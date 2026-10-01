package base

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"testing"
)

func TestPreparedGrowthOwnershipAndZeroFill(t *testing.T) {
	dir := t.TempDir()
	original := bytes.Repeat([]byte{73}, 8192)
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
	opened, err := a.OpenFile("db/data", os.O_RDWR, 0)
	if err != nil {
		t.Fatal(err)
	}
	f := opened.(*memFile)
	mapped := &f.node.data[0]
	if err := f.Truncate(11); err != nil {
		t.Fatal(err)
	}
	if err := f.Truncate(8192); err != nil {
		t.Fatal(err)
	}
	if &f.node.data[0] != mapped {
		t.Fatal("private mapping unnecessarily replaced")
	}
	if !bytes.Equal(f.node.data[:11], original[:11]) || !bytes.Equal(f.node.data[11:], make([]byte, 8181)) {
		t.Fatal("mapped truncate/regrow stale bytes")
	}
	if _, err := f.WriteAt([]byte("child"), 16000); err != nil {
		t.Fatal(err)
	}
	if &f.node.data[0] == mapped {
		t.Fatal("growth beyond mapping did not detach")
	}
	if !bytes.Equal(f.node.data[8192:16000], make([]byte, 7808)) || string(f.node.data[16000:]) != "child" {
		t.Fatal("detached growth content")
	}
	if len(ma.mappings) != 1 {
		t.Fatal("mapping lifetime bookkeeping lost")
	}
	if err := a.Rename("db/data", "db/changed"); err != nil {
		t.Fatal(err)
	}
	if err := ma.Close(); err != nil {
		t.Fatal(err)
	}
	// The detached Go-owned bytes survive unmapping the old storage.
	if string(f.node.data[16000:]) != "child" {
		t.Fatal("detached memory changed")
	}
	check, err := b.OpenFile("db/data", os.O_RDONLY, 0)
	if err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(check)
	if err != nil || !bytes.Equal(got, original) {
		t.Fatal("child B mutated")
	}
	base, err := os.ReadFile(filepath.Join(dir, "data"))
	if err != nil || !bytes.Equal(base, original) {
		t.Fatal("prepared base mutated")
	}
}
