package base

import (
	"encoding/binary"
	"errors"
	"os"
	"path"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
)

// Gate a rename between relative-path resolution and opening, deterministically.
// A directory descriptor must continue to identify its opened directory.
type renameBetweenResolveAndOpen struct {
	*MemFS
	armed bool
}

func TestRelativeDirectoryMovedParentIdentity(t *testing.T) {
	fs := NewMemFS()
	fs.MkdirAll("a/sub", 0700)
	fs.Mkdir("b", 0700)
	fs.WriteFile("a/peer", []byte("old parent"), 0600)
	fs.WriteFile("b/peer", []byte("new parent"), 0600)
	fs.WriteFile("a/sub/value", []byte("original"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	dir := relativeOpen(t, w, m, 3, "a/sub", 2)
	if err := fs.Rename("a/sub", "b/sub"); err != nil {
		t.Fatal(err)
	}
	fs.Mkdir("a/sub", 0700)
	fs.WriteFile("a/sub/value", []byte("replacement"), 0600)
	if got := readFD(t, w, relativeOpen(t, w, m, dir, "value", 0)); got != "original" {
		t.Fatal(got)
	}
	if got := readFD(t, w, relativeOpen(t, w, m, dir, "../peer", 0)); got != "new parent" {
		t.Fatal(got)
	}
	if err := fs.Rename("b", "b/sub/cycle"); !errors.Is(err, syscall.EINVAL) {
		t.Fatalf("directory cycle accepted: %v", err)
	}
	if got := readFD(t, w, relativeOpen(t, w, m, dir, "../peer", 0)); got != "new parent" {
		t.Fatal(got)
	}
}

func (f *renameBetweenResolveAndOpen) DirectoryPath(d *memFile) (string, bool) {
	p, ok := directoryPathForTest(f.MemFS, d)
	if ok && f.armed {
		f.armed = false
		if err := f.Rename("a", "original"); err != nil {
			panic(err)
		}
		if err := f.Mkdir("a", 0700); err != nil {
			panic(err)
		}
		if err := f.WriteFile("a/value", []byte("replacement"), 0600); err != nil {
			panic(err)
		}
	}
	return p, ok
}

// New operation hook: mutate after the directory object is pinned. The same
// rename/name-reuse event is still mandatory; passing by skipping it is invalid.
func (f *renameBetweenResolveAndOpen) PinDirectory(file File) (*Directory, error) {
	d, err := f.MemFS.PinDirectory(file)
	if err != nil {
		return nil, err
	}
	if mf, ok := file.(*memFile); ok {
		f.DirectoryPath(mf)
	}
	return d, nil
}
func directoryPathForTest(fs *MemFS, file *memFile) (string, bool) {
	fs.mu.Lock()
	defer fs.mu.Unlock()
	var result string
	found := false
	var walk func(*memNode, string)
	walk = func(n *memNode, p string) {
		if n == file.node {
			result = p
			found = true
			return
		}
		for k, c := range n.children {
			walk(c, path.Join(p, k))
		}
	}
	walk(fs.root, "/")
	return result, found
}
func TestRelativeDirectoryIdentityDuringRename(t *testing.T) {
	fs := &renameBetweenResolveAndOpen{MemFS: NewMemFS()}
	if err := fs.Mkdir("a", 0700); err != nil {
		t.Fatal(err)
	}
	if err := fs.WriteFile("a/value", []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	w := DefaultWASI()
	w.SetFS(fs)
	dir, rc := w.pathOpen("a", 0, 2, (1<<13)|(1<<18)|2, 0)
	if rc != 0 {
		t.Fatal(rc)
	}
	size := &atomic.Uint64{}
	size.Store(65536)
	m := &Module{Memory: make([]byte, 65536), MemSize: size}
	copy(m.Memory, "value")
	fs.armed = true
	rc = OpenRelative(w, m, dir, 0, 0, 5, 0, 2, 0, 0, 128)
	if rc != 0 {
		t.Fatal(rc)
	}
	if fs.armed {
		t.Fatal("rename gate was not exercised")
	}
	fd := int32(binary.LittleEndian.Uint32(m.Memory[128:]))
	w.mu.Lock()
	f := w.fdTable[fd].f
	w.mu.Unlock()
	b := make([]byte, 32)
	n, err := f.Read(b)
	if n == 0 && err != nil {
		t.Fatal(err)
	}
	if string(b[:n]) != "original" {
		t.Fatalf("directory FD rebound by pathname: got %q, want original", b[:n])
	}
	_ = w.Fd_close(m, fd)
	_ = w.Fd_close(m, dir)
}

func relativeTestModule() *Module {
	size := &atomic.Uint64{}
	size.Store(65536)
	return &Module{Memory: make([]byte, 65536), MemSize: size}
}
func relativeOpen(t *testing.T, w *WasiStubs, m *Module, dir int32, p string, oflags int32) int32 {
	t.Helper()
	copy(m.Memory, p)
	rc := OpenRelative(w, m, dir, 0, 0, int32(len(p)), oflags, 2, 0, 0, 128)
	if rc != 0 {
		t.Fatalf("openat %q: errno %d", p, rc)
	}
	return int32(binary.LittleEndian.Uint32(m.Memory[128:]))
}
func readFD(t *testing.T, w *WasiStubs, fd int32) string {
	t.Helper()
	w.mu.Lock()
	f := w.fdTable[fd].f
	w.mu.Unlock()
	b := make([]byte, 64)
	n, err := f.Read(b)
	if n == 0 && err != nil {
		t.Fatal(err)
	}
	return string(b[:n])
}
func TestRelativeDirectoryRenameNestedAndParent(t *testing.T) {
	fs := NewMemFS()
	fs.MkdirAll("a/sub", 0700)
	fs.WriteFile("a/sub/value", []byte("original"), 0600)
	fs.WriteFile("a/peer", []byte("parent"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	dir := relativeOpen(t, w, m, 3, "a", 2)
	sub := relativeOpen(t, w, m, dir, "sub", 2)
	if err := fs.Rename("a", "moved"); err != nil {
		t.Fatal(err)
	}
	fs.MkdirAll("a/sub", 0700)
	fs.WriteFile("a/sub/value", []byte("replacement"), 0600)
	if got := readFD(t, w, relativeOpen(t, w, m, dir, "sub/value", 0)); got != "original" {
		t.Fatal(got)
	}
	if got := readFD(t, w, relativeOpen(t, w, m, sub, "../peer", 0)); got != "parent" {
		t.Fatal(got)
	}
	copy(m.Memory, "missing/../peer")
	if rc := OpenRelative(w, m, dir, 0, 0, 15, 0, 2, 0, 0, 128); rc != _wasiENOENT {
		t.Fatalf("missing component erased: %d", rc)
	}
}
func TestRelativeDirectoryUnlinkAndNameReuse(t *testing.T) {
	fs := NewMemFS()
	fs.Mkdir("empty", 0700)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	dir := relativeOpen(t, w, m, 3, "empty", 2)
	if err := fs.Remove("empty"); err != nil {
		t.Fatal(err)
	}
	fs.Mkdir("empty", 0700)
	fs.WriteFile("empty/value", []byte("replacement"), 0600)
	copy(m.Memory, ".")
	if rc := StatRelative(w, m, dir, 0, 0, 1, 128); rc != 0 {
		t.Fatal(rc)
	}
	relativeOpen(t, w, m, dir, ".", 2)
	copy(m.Memory, "value")
	if rc := OpenRelative(w, m, dir, 0, 0, 5, 0, 2, 0, 0, 128); rc != _wasiENOENT {
		t.Fatalf("unlinked directory reached replacement: %d", rc)
	}
	copy(m.Memory, "new")
	if rc := OpenRelative(w, m, dir, 0, 0, 3, 1, 2, 0, 0, 128); rc != _wasiENOENT {
		t.Fatalf("created in removed directory: %d", rc)
	}
}
func TestRelativeFileUnlinkKeepsOpenObject(t *testing.T) {
	fs := NewMemFS()
	fs.WriteFile("value", []byte("original"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	fd := relativeOpen(t, w, m, 3, "value", 0)
	fs.Remove("value")
	fs.WriteFile("value", []byte("replacement"), 0600)
	if got := readFD(t, w, fd); got != "original" {
		t.Fatal(got)
	}
}
func TestRelativeDirectoryCloseAndFDReuse(t *testing.T) {
	fs := NewMemFS()
	fs.MkdirAll("a", 0700)
	fs.WriteFile("a/value", []byte("a"), 0600)
	fs.MkdirAll("b", 0700)
	fs.WriteFile("b/value", []byte("b"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	a := relativeOpen(t, w, m, 3, "a", 2)
	b := relativeOpen(t, w, m, 3, "b", 2)
	if rc := w.Fd_close(m, a); rc != 0 {
		t.Fatal(rc)
	}
	copy(m.Memory, "value")
	if rc := OpenRelative(w, m, a, 0, 0, 5, 0, 2, 0, 0, 128); rc != _wasiEBADF {
		t.Fatal(rc)
	}
	if rc := w.Fd_dup2(m, b, a); rc != 0 {
		t.Fatal(rc)
	}
	if got := readFD(t, w, relativeOpen(t, w, m, a, "value", 0)); got != "b" {
		t.Fatal(got)
	}
	if rc := w.Fd_close(m, 3); rc != 0 {
		t.Fatal(rc)
	}
	copy(m.Memory, "a")
	if rc := OpenRelative(w, m, 3, 0, 0, 1, 2, 2, 0, 0, 128); rc != _wasiEBADF {
		t.Fatalf("preopen resurrected: %d", rc)
	}
	if rc := w.Fd_dup2(m, b, 3); rc != 0 {
		t.Fatal(rc)
	}
	if got := readFD(t, w, relativeOpen(t, w, m, 3, "value", 0)); got != "b" {
		t.Fatal(got)
	}
}
func TestRelativeDirectoryConcurrentRename(t *testing.T) {
	fs := NewMemFS()
	fs.Mkdir("a", 0700)
	fs.WriteFile("a/value", []byte("original"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	dir := relativeOpen(t, w, m, 3, "a", 2)
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < 200; i++ {
			if err := fs.Rename("a", "moving"); err != nil {
				panic(err)
			}
			fs.Mkdir("a", 0700)
			fs.WriteFile("a/value", []byte("replacement"), 0600)
			fs.Remove("a/value")
			fs.Remove("a")
			if err := fs.Rename("moving", "a"); err != nil {
				panic(err)
			}
		}
	}()
	for i := 0; i < 200; i++ {
		fd := relativeOpen(t, w, m, dir, "value", 0)
		if got := readFD(t, w, fd); got != "original" {
			t.Fatal(got)
		}
		w.Fd_close(m, fd)
	}
	wg.Wait()
}
func TestRelativeDirectoryStatReadlinkAndInvalidFD(t *testing.T) {
	fs := NewMemFS()
	fs.Mkdir("a", 0700)
	fs.WriteFile("a/value", []byte("original"), 0600)
	w := DefaultWASI()
	w.SetFS(fs)
	m := relativeTestModule()
	dir := relativeOpen(t, w, m, 3, "a", 2)
	fs.Rename("a", "old")
	fs.Mkdir("a", 0700)
	fs.WriteFile("a/value", []byte("wrong length"), 0600)
	copy(m.Memory, "value")
	if rc := StatRelative(w, m, dir, 0, 0, 5, 128); rc != 0 {
		t.Fatal(rc)
	}
	if got := binary.LittleEndian.Uint64(m.Memory[160:]); got != 8 {
		t.Fatalf("wrong stat identity: %d", got)
	}
	if rc := ReadlinkRelative(w, m, dir, 0, 5, 256, 16, 128); rc != _wasiEINVAL {
		t.Fatal(rc)
	}
	file := relativeOpen(t, w, m, dir, "value", 0)
	copy(m.Memory, "value")
	if rc := OpenRelative(w, m, file, 0, 0, 5, 0, 2, 0, 0, 128); rc != _wasiENOTDIR {
		t.Fatal(rc)
	}
	if rc := OpenRelative(w, m, 999, 0, 0, 5, 0, 2, 0, 0, 128); rc != _wasiEBADF {
		t.Fatal(rc)
	}
	if _, err := fs.OpenFile("old/value", os.O_RDONLY, 0); err != nil {
		t.Fatal(err)
	}
}
