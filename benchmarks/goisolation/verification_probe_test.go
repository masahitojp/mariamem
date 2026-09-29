package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/masahitojp/mariamem/internal/snapshot"
)

func TestHashExperimentFailsClosedWithIdenticalInventory(t *testing.T) {
	root := t.TempDir()
	items := []hashItem{}
	for _, name := range []string{"redo", "undo", "sidecar"} {
		path := filepath.Join(root, name)
		data := []byte("verified " + name)
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}
		digest, err := snapshot.Digest(path)
		if err != nil {
			t.Fatal(err)
		}
		items = append(items, hashItem{path, int64(len(data)), digest})
	}
	for _, workers := range []int{1, 2, 4} {
		if err := hashItems(items, workers); err != nil {
			t.Fatal(err)
		}
	}
	// Same size: a metadata-only shortcut must not hide corrupted content.
	if err := os.WriteFile(items[0].Path, []byte("corrupt! redo"), 0600); err != nil {
		t.Fatal(err)
	}
	for _, workers := range []int{1, 2, 4} {
		if err := hashItems(items, workers); err == nil {
			t.Fatal("corruption accepted")
		}
	}
	if err := os.Remove(items[1].Path); err != nil {
		t.Fatal(err)
	}
	if err := hashItems(items[1:], 4); err == nil {
		t.Fatal("missing file accepted")
	}
	if err := hashItems(items, 0); err == nil {
		t.Fatal("invalid workers accepted")
	}
}
