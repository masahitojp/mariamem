package base

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"syscall"
	"testing"

	"github.com/masahitojp/mariamem/internal/prepared"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
)

func ownedFileMappings(t *testing.T) uint64 {
	t.Helper()
	helper := os.Getenv("MARIAMEM_PROCESS_COST")
	if helper == "" {
		t.Log("OS file-map counter omitted; acceptance sets MARIAMEM_PROCESS_COST")
		return 0
	}
	pid := strconv.Itoa(os.Getpid())
	b, e := exec.Command(helper, pid).Output()
	if e != nil {
		t.Fatal(e)
	}
	var result map[string]struct {
		Bytes uint64 `json:"file_mapping_bytes"`
		Error string `json:"error"`
	}
	if e = json.Unmarshal(b, &result); e != nil {
		t.Fatal(e)
	}
	value, ok := result[pid]
	if !ok || value.Error != "" {
		t.Fatalf("OS mapping counters unavailable: %s", b)
	}
	return value.Bytes
}

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
	before := ownedFileMappings(t)
	for i := 0; i < 100; i++ {
		if p, e := MapPreparedHandles(NewMemFS(), entries, "db"); e == nil || p != nil {
			t.Fatal("partial mapping accepted")
		}
	}
	after := ownedFileMappings(t)
	t.Logf("100 partial mapping failures: file-backed VM bytes %d -> %d", before, after)
	if after != before {
		t.Fatal("partial mapping failure retained file-backed VM")
	}
}

// The descriptor remains the same file after its name disappears. Child file
// identity, truncate/regrow and growth still follow the existing MemFS contract.
func TestOwnedMappedTruncateRenameUnlinkIdentity(t *testing.T) {
	original := bytes.Repeat([]byte{73}, 8192)
	name := filepath.Join(t.TempDir(), "backing")
	if err := os.WriteFile(name, original, 0600); err != nil {
		t.Fatal(err)
	}
	f, err := os.Open(name)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err = os.Remove(name); err != nil {
		t.Fatal(err)
	}
	entries := []prepared.Entry{{Name: ".", Directory: true, FD: -1}, {Name: "seed", FD: int(f.Fd()), Size: 8192}}
	a, b := NewMemFS(), NewMemFS()
	ma, err := MapPreparedHandles(a, entries, "db")
	if err != nil {
		t.Fatal(err)
	}
	defer ma.Close()
	mb, err := MapPreparedHandles(b, entries, "db")
	if err != nil {
		t.Fatal(err)
	}
	defer mb.Close()
	opened, err := a.OpenFile("db/seed", os.O_RDWR, 0)
	if err != nil {
		t.Fatal(err)
	}
	child := opened.(*memFile)
	defer child.Close()
	mapped := &child.node.data[0]
	if err = child.Truncate(11); err != nil {
		t.Fatal(err)
	}
	if err = child.Truncate(8192); err != nil {
		t.Fatal(err)
	}
	if &child.node.data[0] != mapped || !bytes.Equal(child.node.data[:11], original[:11]) || !bytes.Equal(child.node.data[11:], make([]byte, 8181)) {
		t.Fatal("mapped truncate/regrow contract changed")
	}
	if _, err = child.WriteAt([]byte("child"), 16000); err != nil {
		t.Fatal(err)
	}
	if &child.node.data[0] == mapped || !bytes.Equal(child.node.data[8192:16000], make([]byte, 7808)) {
		t.Fatal("growth did not detach/zero-fill")
	}
	if err = a.Rename("db/seed", "db/changed"); err != nil {
		t.Fatal(err)
	}
	if err = a.Remove("db/changed"); err != nil {
		t.Fatal(err)
	}
	replacement, err := a.OpenFile("db/seed", os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	defer replacement.Close()
	if replacement.(*memFile).node == child.node {
		t.Fatal("name reuse changed open file identity")
	}
	if err = ma.Close(); err != nil {
		t.Fatal(err)
	}
	if string(child.node.data[16000:]) != "child" {
		t.Fatal("detached open file lost contents")
	}
	other, err := b.OpenFile("db/seed", os.O_RDONLY, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer other.Close()
	got, err := io.ReadAll(other)
	if err != nil || !bytes.Equal(got, original) {
		t.Fatal("sibling changed", err)
	}
	got = make([]byte, len(original))
	if _, err = f.ReadAt(got, 0); err != nil || !bytes.Equal(got, original) {
		t.Fatal("owned backing changed", err)
	}
}
