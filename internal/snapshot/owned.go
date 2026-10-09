package snapshot

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"reflect"
	"sort"
	"sync"
	"syscall"

	"github.com/masahitojp/mariamem/internal/prepared"
)

// Owned pins a completely verified template. No path is used after acquisition.
// Later media corruption is not rehashed at Fork. Not a same-UID security boundary.
type Owned struct {
	mu       sync.RWMutex
	manifest Manifest
	entries  []prepared.Entry
	files    []*os.File
	closed   bool
	closeErr error
}

func readManifest(root, build string) (Manifest, error) {
	var m Manifest
	for _, name := range []string{root, filepath.Join(root, "manifest.json")} {
		st, e := os.Lstat(name)
		if e != nil {
			return m, e
		}
		if name == root && !st.IsDir() || name != root && !st.Mode().IsRegular() {
			return m, errors.New("invalid snapshot root or manifest")
		}
	}
	children, e := os.ReadDir(root)
	if e != nil {
		return m, e
	}
	if len(children) != 2 || children[0].Name() != "data" || children[1].Name() != "manifest.json" {
		return m, errors.New("snapshot must contain only data and manifest.json")
	}
	b, e := os.ReadFile(filepath.Join(root, "manifest.json"))
	if e != nil {
		return m, e
	}
	if e = json.Unmarshal(b, &m); e != nil {
		return m, e
	}
	return m, checkManifest(m, build)
}
func checkManifest(m Manifest, build string) error {
	if m.Format != "mariamem-cold-snapshot" || m.Version != 1 || m.Storage != "memory" || m.WASM != build {
		return errors.New("snapshot format or WASM build mismatch")
	}
	root, ok := m.Entries["."]
	if !ok || root.Kind != "directory" {
		return errors.New("missing snapshot data root")
	}
	for name, e := range m.Entries {
		if name != "." && (name == "" || path.IsAbs(name) || path.Clean(name) != name || name == ".." || len(name) >= 3 && name[:3] == "../") {
			return fmt.Errorf("invalid snapshot entry: %q", name)
		}
		if e.Kind == "directory" {
			if e.Bytes != nil || e.SHA256 != "" {
				return errors.New("invalid directory entry")
			}
		} else if e.Kind == "file" {
			h, err := hex.DecodeString(e.SHA256)
			if e.Bytes == nil || *e.Bytes < 0 || err != nil || len(h) != 32 || name == "." {
				return errors.New("invalid file entry")
			}
		} else {
			return errors.New("invalid snapshot entry kind")
		}
		if name != "." {
			parent, ok := m.Entries[path.Dir(name)]
			if !ok || parent.Kind != "directory" {
				return errors.New("missing snapshot parent directory")
			}
		}
	}
	return nil
}

// Import reads external files into a fresh private copy; it never edits the input.
// The copied bytes are checked against the captured external manifest. A digest
// produced from the copy is never substituted for the expected external digest.
func Import(root, build string) (*Owned, error) {
	m, e := readManifest(root, build)
	if e != nil {
		return nil, e
	}
	temp, e := os.MkdirTemp("", "mariamem-import-")
	if e != nil {
		return nil, e
	}
	defer os.RemoveAll(temp)
	source := filepath.Join(root, "data")
	e = filepath.WalkDir(source, func(name string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		st, err := d.Info()
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(source, name)
		if err != nil {
			return err
		}
		dest := filepath.Join(temp, "data", rel)
		if st.IsDir() {
			return os.Mkdir(dest, 0700)
		}
		if !st.Mode().IsRegular() {
			return errors.New("snapshot contains link or special file")
		}
		fd, err := syscall.Open(name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
		if err != nil {
			return err
		}
		in := os.NewFile(uintptr(fd), name)
		defer in.Close()
		opened, err := in.Stat()
		if err != nil {
			return err
		}
		if !opened.Mode().IsRegular() {
			return errors.New("snapshot input is not regular")
		}
		out, err := os.OpenFile(dest, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			return err
		}
		_, err = io.Copy(out, in)
		return errors.Join(err, out.Close())
	})
	if e != nil {
		return nil, e
	}
	return adopt(temp, m)
}

// AdoptCreated takes only a newly created implementation-owned directory, after
// all producer writers have stopped. External imports must use Import instead.
func AdoptCreated(root, build string) (*Owned, error) {
	m, e := readManifest(root, build)
	if e != nil {
		return nil, e
	}
	return adopt(root, m)
}
func adopt(root string, m Manifest) (result *Owned, err error) {
	o := &Owned{manifest: m}
	defer func() {
		if err != nil {
			err = errors.Join(err, o.Close())
		}
	}()
	actual := map[string]Entry{}
	names := []string{}
	source := filepath.Join(root, "data")
	err = filepath.WalkDir(source, func(name string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		st, e := d.Info()
		if e != nil {
			return e
		}
		rel, e := filepath.Rel(source, name)
		if e != nil {
			return e
		}
		rel = filepath.ToSlash(rel)
		if st.IsDir() {
			actual[rel] = Entry{Kind: "directory"}
			o.entries = append(o.entries, prepared.Entry{Name: rel, FD: -1, Directory: true})
			return nil
		}
		if !st.Mode().IsRegular() {
			return errors.New("snapshot contains link or special file")
		}
		fd, e := syscall.Open(name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
		if e != nil {
			return e
		}
		f := os.NewFile(uintptr(fd), name)
		o.files = append(o.files, f)
		opened, e := f.Stat()
		if e != nil {
			return e
		}
		if !opened.Mode().IsRegular() {
			return errors.New("snapshot backing is not regular")
		}
		size := opened.Size()
		actual[rel] = Entry{Kind: "file", Bytes: &size}
		o.entries = append(o.entries, prepared.Entry{Name: rel, Size: size, FD: fd})
		names = append(names, name)
		return nil
	})
	if err != nil {
		return nil, err
	}
	// Remove all ordinary path aliases BEFORE final verification of retained FDs.
	for _, name := range names {
		if err = os.Remove(name); err != nil {
			return nil, err
		}
	}
	if err = os.RemoveAll(root); err != nil {
		return nil, err
	}
	hashes := make([]string, len(o.entries))
	err = VerifyIndependent(len(o.entries), func(i int) error {
		v := o.entries[i]
		if v.Directory {
			return nil
		}
		f := fileFor(o.files, v.FD)
		if f == nil {
			return errors.New("missing owned descriptor")
		}
		st, e := f.Stat()
		if e != nil {
			return e
		}
		if st.Sys().(*syscall.Stat_t).Nlink != 0 {
			return errors.New("owned backing retains path aliases")
		}
		h := sha256.New()
		n, e := io.Copy(h, io.NewSectionReader(f, 0, v.Size))
		if e != nil {
			return e
		}
		if n != v.Size {
			return io.ErrUnexpectedEOF
		}
		hashes[i] = hex.EncodeToString(h.Sum(nil))
		return nil
	})
	if err != nil {
		return nil, err
	}
	for i, v := range o.entries {
		if !v.Directory {
			entry := actual[v.Name]
			entry.SHA256 = hashes[i]
			actual[v.Name] = entry
		}
	}
	if !reflect.DeepEqual(actual, m.Entries) {
		return nil, errors.New("snapshot file manifest mismatch")
	}
	return o, nil
}
func fileFor(files []*os.File, fd int) *os.File {
	for _, f := range files {
		if int(f.Fd()) == fd {
			return f
		}
	}
	return nil
}

// Acquire pins descriptor identity, checks cheap metadata, and returns borrowed
// entries. It performs no inventory walk or content hashing.
func (o *Owned) Acquire(build string) ([]prepared.Entry, func(), error) {
	o.mu.RLock()
	fail := func(e error) ([]prepared.Entry, func(), error) { o.mu.RUnlock(); return nil, nil, e }
	if o.closed {
		return fail(errors.New("snapshot is closed"))
	}
	if e := checkManifest(o.manifest, build); e != nil {
		return fail(e)
	}
	for _, v := range o.entries {
		if v.Directory {
			continue
		}
		f := fileFor(o.files, v.FD)
		if f == nil {
			return fail(errors.New("missing owned descriptor"))
		}
		st, e := f.Stat()
		if e != nil {
			return fail(e)
		}
		if !st.Mode().IsRegular() || st.Size() != v.Size || st.Sys().(*syscall.Stat_t).Nlink != 0 {
			return fail(errors.New("owned snapshot metadata changed"))
		}
	}
	return append([]prepared.Entry(nil), o.entries...), o.mu.RUnlock, nil
}
func (o *Owned) Close() error {
	if o == nil {
		return nil
	}
	o.mu.Lock()
	defer o.mu.Unlock()
	if o.closed {
		return o.closeErr
	}
	o.closed = true
	for _, f := range o.files {
		o.closeErr = errors.Join(o.closeErr, f.Close())
	}
	o.files = nil
	o.entries = nil
	return o.closeErr
}

type Descriptor struct {
	Name string `json:"name"`
	FD   int    `json:"fd"`
}
type Handoff struct {
	Manifest Manifest     `json:"manifest"`
	Files    []Descriptor `json:"files"`
}

// ReceiveInherited accepts only implementation-owned unlinked, read-only handles.
// Python's creation/import gate already verified their content. This is an
// internal process handoff, not a public bypass for arbitrary path validation.
func ReceiveInherited(h Handoff, build string) (result *Owned, err error) {
	o := &Owned{manifest: h.Manifest}
	defer func() {
		if err != nil {
			err = errors.Join(err, o.Close())
		}
	}()
	descriptors := map[string]int{}
	seen := map[int]bool{}
	var malformed error
	for _, v := range h.Files {
		if v.FD < 3 || seen[v.FD] {
			malformed = errors.New("invalid inherited descriptor")
			continue
		}
		seen[v.FD] = true
		syscall.CloseOnExec(v.FD)
		f := os.NewFile(uintptr(v.FD), v.Name)
		o.files = append(o.files, f)
		if _, ok := descriptors[v.Name]; ok {
			malformed = errors.New("duplicate inherited name")
		}
		descriptors[v.Name] = v.FD
	}
	if malformed != nil {
		return nil, malformed
	}
	if err = checkManifest(h.Manifest, build); err != nil {
		return nil, err
	}
	names := make([]string, 0, len(h.Manifest.Entries))
	for name := range h.Manifest.Entries {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		e := h.Manifest.Entries[name]
		if e.Kind == "directory" {
			o.entries = append(o.entries, prepared.Entry{Name: name, FD: -1, Directory: true})
			continue
		}
		fd, ok := descriptors[name]
		if !ok {
			return nil, errors.New("missing inherited file")
		}
		delete(descriptors, name)
		f := fileFor(o.files, fd)
		st, e2 := f.Stat()
		if e2 != nil {
			return nil, e2
		}
		flags, _, errno := syscall.Syscall(syscall.SYS_FCNTL, uintptr(fd), syscall.F_GETFL, 0)
		if errno != 0 {
			return nil, errno
		}
		if flags&syscall.O_ACCMODE != syscall.O_RDONLY || !st.Mode().IsRegular() || st.Size() != *e.Bytes || st.Sys().(*syscall.Stat_t).Nlink != 0 {
			return nil, errors.New("inherited backing is not owned read-only state")
		}
		o.entries = append(o.entries, prepared.Entry{Name: name, Size: *e.Bytes, FD: fd})
	}
	if len(descriptors) != 0 {
		return nil, errors.New("extra inherited files")
	}
	return o, nil
}
