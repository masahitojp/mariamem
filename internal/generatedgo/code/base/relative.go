package base

import (
	"encoding/binary"
	"io/fs"
	"os"
	"path"
	"strings"
	"syscall"
	"time"
)

// This is deliberately an operation interface, not a pathname-producing hook.
// Directory retains the same MemFS node as the open file descriptor. The GC
// keeps an unlinked node alive while a descriptor/operation still references it.
type relativeFileSystem interface {
	OpenFile(string, int, os.FileMode) (File, error)
	Lstat(string) (os.FileInfo, error)
	Readlink(string) (string, error)
}
type Directory struct {
	fs   *MemFS
	node *memNode
}

func (fsys *MemFS) PinDirectory(f File) (*Directory, error) {
	mf, ok := f.(*memFile)
	if !ok || mf.fsys != fsys {
		return nil, syscall.EBADF
	}
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	if !mf.node.dir {
		return nil, syscall.ENOTDIR
	}
	return &Directory{fs: fsys, node: mf.node}, nil
}

// Caller holds the single tree mutex. Resolve components from the held node;
// do not clean away missing/non-directory components before looking them up.
func (d *Directory) lookup(name string) (*memNode, error) {
	if name == "" {
		return nil, fs.ErrNotExist
	}
	n := d.node
	if strings.HasPrefix(name, "/") {
		n = d.fs.root
	}
	for _, part := range strings.Split(name, "/") {
		if part == "" {
			continue
		}
		if !n.dir {
			return nil, syscall.ENOTDIR
		}
		switch part {
		case ".":
		case "..":
			if n.parent != nil {
				n = n.parent
			}
		default:
			c, ok := n.children[part]
			if !ok {
				return nil, fs.ErrNotExist
			}
			n = c
		}
	}
	if strings.HasSuffix(name, "/") && !n.dir {
		return nil, syscall.ENOTDIR
	}
	return n, nil
}
func (d *Directory) parent(name string) (*memNode, string, error) {
	// filepath.Clean/path.Clean would incorrectly erase e.g. missing/../file.
	clean := strings.TrimRight(name, "/")
	i := strings.LastIndex(clean, "/")
	parent, leaf := ".", clean
	if i >= 0 {
		parent, leaf = clean[:i], clean[i+1:]
		if parent == "" {
			parent = "/"
		}
	}
	if leaf == "" || leaf == "." || leaf == ".." {
		return nil, "", syscall.EINVAL
	}
	n, err := d.lookup(parent)
	if err != nil {
		return nil, "", err
	}
	if !n.dir {
		return nil, "", syscall.ENOTDIR
	}
	// Reads/stat of an unlinked directory remain valid, but it cannot receive
	// new entries. Never confuse a replacement entry with this directory.
	if n != d.fs.root && (n.parent == nil || n.parent.children[n.name] != n) {
		return nil, "", fs.ErrNotExist
	}
	return n, leaf, nil
}
func (d *Directory) OpenFile(name string, flag int, perm os.FileMode) (File, error) {
	d.fs.mu.Lock()
	defer d.fs.mu.Unlock()
	n, err := d.lookup(name)
	if err != nil {
		if err != fs.ErrNotExist || flag&os.O_CREATE == 0 {
			return nil, &fs.PathError{Op: "openat", Path: name, Err: err}
		}
		p, leaf, err := d.parent(name)
		if err != nil {
			return nil, &fs.PathError{Op: "openat", Path: name, Err: err}
		}
		n = &memNode{parent: p, name: leaf, mode: perm & 0777, modTime: time.Now()}
		p.children[leaf] = n
	} else if flag&os.O_CREATE != 0 && flag&os.O_EXCL != 0 {
		return nil, fs.ErrExist
	}
	if n.dir && flag&(os.O_WRONLY|os.O_RDWR|os.O_TRUNC) != 0 {
		return nil, syscall.EISDIR
	}
	if flag&os.O_TRUNC != 0 {
		n.data = n.data[:0]
		n.modTime = time.Now()
	}
	f := &memFile{fsys: d.fs, node: n}
	if flag&os.O_APPEND != 0 {
		f.off = int64(len(n.data))
	}
	return f, nil
}
func (d *Directory) Lstat(name string) (os.FileInfo, error) {
	d.fs.mu.Lock()
	defer d.fs.mu.Unlock()
	n, err := d.lookup(name)
	if err != nil {
		return nil, &fs.PathError{Op: "statat", Path: name, Err: err}
	}
	return n.info(), nil
}
func (d *Directory) Readlink(name string) (string, error) {
	d.fs.mu.Lock()
	defer d.fs.mu.Unlock()
	_, err := d.lookup(name)
	if err != nil {
		return "", &fs.PathError{Op: "readlinkat", Path: name, Err: err}
	}
	// MemFS has no symlink nodes. Match readlink on a regular file/directory.
	return "", &fs.PathError{Op: "readlinkat", Path: name, Err: syscall.EINVAL}
}

func relativeDirectory(w *WasiStubs, fd int32) (relativeFileSystem, string, int32) {
	w.mu.Lock()
	op := w.fdTable[fd]
	fsys := w.fsys
	if op == nil {
		w.mu.Unlock()
		return nil, "", _wasiEBADF
	}
	f, dir, label := op.f, op.isDir, op.path
	w.mu.Unlock()
	if !dir {
		return nil, "", _wasiENOTDIR
	}
	binder, ok := fsys.(interface {
		PinDirectory(File) (*Directory, error)
	})
	if !ok {
		return nil, "", _wasiENOTSUP
	} // Never fall back to a stale path string.
	d, err := binder.PinDirectory(f)
	if err != nil {
		return nil, "", mapOSError(err)
	}
	if d.node == d.fs.root {
		return fsys, label, 0
	} // Keep root's virtual devices.
	return d, label, 0
}
func OpenRelative(w *WasiStubs, m *Module, fd, flags, ptr, n, oflags int32, rights, inherited int64, fdflags, out int32) int32 {
	b := w.memSlice(m, ptr, n)
	o := w.memSlice(m, out, 4)
	if b == nil || o == nil {
		return _wasiEFAULT
	}
	f, label, rc := relativeDirectory(w, fd)
	if rc != 0 {
		return rc
	}
	p := string(b)
	id, rc := w.pathOpenOnFS(f, p, path.Join(label, p), flags, oflags, rights, fdflags)
	if rc == 0 {
		binary.LittleEndian.PutUint32(o, uint32(id))
	}
	return rc
}
func ReadlinkRelative(w *WasiStubs, m *Module, fd, ptr, n, buf, size, out int32) int32 {
	b := w.memSlice(m, ptr, n)
	o := w.memSlice(m, out, 4)
	dest := w.memSlice(m, buf, size)
	if b == nil || o == nil || dest == nil {
		return _wasiEFAULT
	}
	f, _, rc := relativeDirectory(w, fd)
	if rc != 0 {
		return rc
	}
	s, err := f.Readlink(string(b))
	if err != nil {
		return mapOSError(err)
	}
	nn := copy(dest, s)
	binary.LittleEndian.PutUint32(o, uint32(nn))
	return 0
}
func StatRelative(w *WasiStubs, m *Module, fd, flags, ptr, n, out int32) int32 {
	b := w.memSlice(m, ptr, n)
	o := w.memSlice(m, out, 64)
	if b == nil || o == nil {
		return _wasiEFAULT
	}
	f, _, rc := relativeDirectory(w, fd)
	if rc != 0 {
		return rc
	}
	st, err := f.Lstat(string(b))
	if err != nil {
		return mapOSError(err)
	}
	writeFilestat(o, st)
	return 0
}
