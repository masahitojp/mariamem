package base

import (
	"io"
	"os"
	"path/filepath"
	"syscall"
	"testing"

	"github.com/masahitojp/mariamem/internal/prepared"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
)

func TestOwnedPrivateViewsGrowthAndRelease(t *testing.T) {
	transfer := t.TempDir()
	if e := os.Mkdir(filepath.Join(transfer, "data"), 0700); e != nil {
		t.Fatal(e)
	}
	original := make([]byte, 8192)
	copy(original, "prepared-state")
	if e := os.WriteFile(filepath.Join(transfer, "data/seed"), original, 0600); e != nil {
		t.Fatal(e)
	}
	destination := filepath.Join(t.TempDir(), "snapshot")
	if e := os.Mkdir(destination, 0700); e != nil {
		t.Fatal(e)
	}
	const build = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	if e := stored.Publish(transfer, destination, build); e != nil {
		t.Fatal(e)
	}
	owned, e := stored.AdoptCreated(destination, build)
	if e != nil {
		t.Fatal(e)
	}
	defer owned.Close()
	views, release, e := owned.Acquire(build)
	if e != nil {
		t.Fatal(e)
	}
	a, b := NewMemFS(), NewMemFS()
	ma, e := MapPreparedHandles(a, views, "db")
	if e != nil {
		t.Fatal(e)
	}
	defer ma.Close()
	mb, e := MapPreparedHandles(b, views, "db")
	if e != nil {
		t.Fatal(e)
	}
	defer mb.Close()
	release()
	f, e := a.OpenFile("db/seed", os.O_RDWR, 0)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = f.Write([]byte("CHILD")); e != nil {
		t.Fatal(e)
	}
	if _, e = f.Seek(0, io.SeekEnd); e != nil {
		t.Fatal(e)
	}
	if _, e = f.Write(make([]byte, 65536)); e != nil {
		t.Fatal(e)
	}
	f.Close()
	check := func() {
		t.Helper()
		f, e := b.OpenFile("db/seed", os.O_RDONLY, 0)
		if e != nil {
			t.Fatal(e)
		}
		got, e := io.ReadAll(f)
		f.Close()
		if e != nil || string(got) != string(original) {
			t.Fatal("sibling contents changed", e)
		}
	}
	check()
	// Owner FD release cannot invalidate existing private child mappings.
	if e = owned.Close(); e != nil {
		t.Fatal(e)
	}
	check()
	view := mb.mappings[0]
	if e = mb.Close(); e != nil {
		t.Fatal(e)
	}
	// A second unmap must fail: syscall removes its mapping record only after
	// a successful OS munmap. mincore is unsuitable here because an unrelated
	// allocator can immediately reuse the virtual address.
	if e = syscall.Munmap(view); e != syscall.EINVAL {
		t.Fatalf("view was not successfully unmapped: %v", e)
	}
	if e = mb.Close(); e != nil {
		t.Fatal(e)
	}
}
func TestOwnedPartialMappingFailure(t *testing.T) {
	f, e := os.CreateTemp(t.TempDir(), "seed")
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	if e = f.Truncate(8192); e != nil {
		t.Fatal(e)
	}
	entries := []prepared.Entry{{Name: ".", FD: -1, Directory: true}, {Name: "seed", FD: int(f.Fd()), Size: 8192}, {Name: "invalid", FD: -1, Size: 8192}}
	for i := 0; i < 100; i++ {
		if p, e := MapPreparedHandles(NewMemFS(), entries, "db"); e == nil || p != nil {
			t.Fatal("partial mapping accepted")
		}
	}
}
