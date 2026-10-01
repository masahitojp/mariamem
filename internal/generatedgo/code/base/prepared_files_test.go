package base

import (
	"io"
	"os"
	"path/filepath"
	"testing"
)

func TestPreparedFilePrivateViews(t *testing.T) {
	dir := t.TempDir()
	original := []byte("prepared-state")
	if err := os.WriteFile(filepath.Join(dir, "data"), original, 0600); err != nil {
		t.Fatal(err)
	}
	a, b := NewMemFS(), NewMemFS()
	ma, err := MapPreparedFiles(a, dir, "db")
	if err != nil {
		t.Fatal(err)
	}
	defer ma.Close()
	mb, err := MapPreparedFiles(b, dir, "db")
	if err != nil {
		t.Fatal(err)
	}
	defer mb.Close()
	f, err := a.OpenFile("db/data", os.O_RDWR, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = f.Write([]byte("CHILD")); err != nil {
		t.Fatal(err)
	}
	f.Close()
	check := func(fs *MemFS) {
		t.Helper()
		f, err := fs.OpenFile("db/data", os.O_RDONLY, 0)
		if err != nil {
			t.Fatal(err)
		}
		defer f.Close()
		got, err := io.ReadAll(f)
		if err != nil || string(got) != string(original) {
			t.Fatalf("base/child changed: %q %v", got, err)
		}
	}
	check(b)
	f, err = a.OpenFile("db/data", os.O_WRONLY|os.O_APPEND, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = f.Write(make([]byte, 65536)); err != nil {
		t.Fatal(err)
	}
	f.Close()
	check(b)
	if err := a.Rename("db/data", "db/renamed"); err != nil {
		t.Fatal(err)
	}
	check(b)
	if err := ma.Close(); err != nil {
		t.Fatal(err)
	}
	check(b)
	base, err := os.ReadFile(filepath.Join(dir, "data"))
	if err != nil || string(base) != string(original) {
		t.Fatalf("base mutated: %q %v", base, err)
	}
}
func TestPreparedFilesRejectPartialInvalidTree(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "a"), []byte("map-before-failure"), 0600)
	if err := os.Symlink("a", filepath.Join(dir, "z")); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 30; i++ {
		// A failed setup's incomplete tree is discarded, never entered by a guest.
		maps, err := MapPreparedFiles(NewMemFS(), dir, "db")
		if err == nil || maps != nil {
			t.Fatal("invalid prepared tree accepted")
		}
	}
}
