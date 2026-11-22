package snapshot

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestWindowsSnapshotFileOwnership(t *testing.T) {
	root := t.TempDir()
	name := filepath.Join(root, "seed")
	if err := os.WriteFile(name, []byte("seed"), 0600); err != nil {
		t.Fatal(err)
	}
	f, err := openSnapshotFile(name)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		t.Fatal(err)
	}
	if snapshotUnlinked(f, st) {
		t.Fatal("named file accepted as unlinked")
	}
	if ro, err := snapshotReadOnly(int(f.Fd())); err != nil || !ro {
		t.Fatalf("read-only proof: %v %v", ro, err)
	}
	if err := snapshotCloseOnExec(int(f.Fd())); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(name); err != nil {
		t.Fatal(err)
	}
	if !snapshotUnlinked(f, st) {
		t.Fatal("detached backing not recognized")
	}
	data := make([]byte, 4)
	if _, err := f.ReadAt(data, 0); err != nil || string(data) != "seed" {
		t.Fatalf("retained read: %q %v", data, err)
	}
	writable, err := os.Create(filepath.Join(root, "writable"))
	if err != nil {
		t.Fatal(err)
	}
	defer writable.Close()
	if ro, err := snapshotReadOnly(int(writable.Fd())); err != nil || ro {
		t.Fatalf("writable accepted: %v %v", ro, err)
	}
}

func TestWindowsSnapshotRejectsSurvivingHardlink(t *testing.T) {
	root := t.TempDir()
	name := filepath.Join(root, "seed")
	alias := filepath.Join(root, "alias")
	if err := os.WriteFile(name, []byte("seed"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Link(name, alias); err != nil {
		t.Fatal(err)
	}
	f, err := openSnapshotFile(name)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := os.Remove(name); err != nil {
		t.Fatal(err)
	}
	st, err := f.Stat()
	if err != nil {
		t.Fatal(err)
	}
	if snapshotUnlinked(f, st) {
		t.Fatal("surviving hardlink accepted")
	}
}

func TestWindowsSnapshotImport(t *testing.T) {
	const build = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	root := t.TempDir()
	data := filepath.Join(root, "data")
	if err := os.Mkdir(data, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(data, "seed"), []byte("seed"), 0600); err != nil {
		t.Fatal(err)
	}
	entries, err := Inventory(data)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := json.Marshal(Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: build, Storage: "memory", Entries: entries})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "manifest.json"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	owned, err := Import(root, build)
	if err != nil {
		t.Fatal(err)
	}
	views, release, err := owned.Acquire(build)
	if err != nil {
		owned.Close()
		t.Fatal(err)
	}
	if len(views) != 2 {
		release()
		owned.Close()
		t.Fatalf("entries: %v", views)
	}
	release()
	if err := owned.Close(); err != nil {
		t.Fatal(err)
	}
	if _, _, err := owned.Acquire(build); err == nil {
		t.Fatal("closed snapshot accepted")
	}
}
