package snapshot

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"testing"
	"time"
)

const testOwnedBuild = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func externalTemplate(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	data := filepath.Join(root, "data")
	if e := os.Mkdir(data, 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(data, "seed"), []byte("prepared-state"), 0600); e != nil {
		t.Fatal(e)
	}
	entries, e := Inventory(data)
	if e != nil {
		t.Fatal(e)
	}
	writeOwnedManifest(t, root, Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: testOwnedBuild, Storage: "memory", Entries: entries})
	return root
}
func writeOwnedManifest(t *testing.T, root string, m Manifest) {
	t.Helper()
	b, e := json.Marshal(m)
	if e != nil {
		t.Fatal(e)
	}
	if e = os.WriteFile(filepath.Join(root, "manifest.json"), b, 0600); e != nil {
		t.Fatal(e)
	}
}
func ownedFDCount(t *testing.T) int {
	t.Helper()
	if runtime.GOOS == "linux" {
		entries, e := os.ReadDir("/proc/self/fd")
		if e != nil {
			t.Fatal(e)
		}
		return len(entries)
	}
	var limit syscall.Rlimit
	if e := syscall.Getrlimit(syscall.RLIMIT_NOFILE, &limit); e != nil {
		t.Fatal(e)
	}
	count := 0
	for fd := uint64(0); fd < limit.Cur; fd++ {
		_, _, e := syscall.Syscall(syscall.SYS_FCNTL, uintptr(fd), syscall.F_GETFD, 0)
		if e == 0 {
			count++
		}
	}
	return count
}

func TestOwnedImportRejectsChangedInput(t *testing.T) {
	for _, kind := range []string{"content", "extra", "missing", "size", "link", "manifest", "guest", "format"} {
		t.Run(kind, func(t *testing.T) {
			root := externalTemplate(t)
			build := testOwnedBuild
			switch kind {
			case "content":
				os.WriteFile(filepath.Join(root, "data/seed"), []byte("CHANGED!-state"), 0600)
			case "extra":
				os.WriteFile(filepath.Join(root, "data/extra"), []byte("x"), 0600)
			case "missing":
				os.Remove(filepath.Join(root, "data/seed"))
			case "size":
				os.Truncate(filepath.Join(root, "data/seed"), 1)
			case "link":
				os.Remove(filepath.Join(root, "data/seed"))
				os.Symlink("/dev/null", filepath.Join(root, "data/seed"))
			case "manifest":
				os.WriteFile(filepath.Join(root, "manifest.json"), []byte("{invalid"), 0600)
			case "guest":
				build = strings.Repeat("b", 64)
			case "format":
				m, e := readManifest(root, build)
				if e != nil {
					t.Fatal(e)
				}
				m.Version = 2
				writeOwnedManifest(t, root, m)
			}
			if o, e := Import(root, build); e == nil {
				o.Close()
				t.Fatal("invalid input accepted")
			}
		})
	}
}
func TestOwnedImportDetachedAndPinned(t *testing.T) {
	root := externalTemplate(t)
	o, e := Import(root, testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	defer o.Close()
	views, release, e := o.Acquire(testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	fd := -1
	for _, v := range views {
		if !v.Directory {
			fd = v.FD
		}
	}
	if e = os.WriteFile(filepath.Join(root, "data/seed"), []byte("changed externally"), 0600); e != nil {
		t.Fatal(e)
	}
	if e = os.RemoveAll(root); e != nil {
		t.Fatal(e)
	}
	got := make([]byte, len("prepared-state"))
	if _, e = syscall.Pread(fd, got, 0); e != nil || string(got) != "prepared-state" {
		t.Fatalf("external change affected owned backing: %q %v", got, e)
	}
	started, done := make(chan struct{}), make(chan error, 1)
	go func() { close(started); done <- o.Close() }()
	<-started
	select {
	case e := <-done:
		t.Fatalf("Close returned while pinned: %v", e)
	case <-time.After(20 * time.Millisecond):
	}
	release()
	if e = <-done; e != nil {
		t.Fatal(e)
	}
	var st syscall.Stat_t
	if e = syscall.Fstat(fd, &st); e != syscall.EBADF {
		t.Fatalf("descriptor retained: %v", e)
	}
	if _, _, e = o.Acquire(testOwnedBuild); e == nil {
		t.Fatal("closed template acquired")
	}
}
func TestOwnedFailureAndCloseNoFDLeak(t *testing.T) {
	root := externalTemplate(t)
	warm, e := Import(root, testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	warm.Close()
	before := ownedFDCount(t)
	for i := 0; i < 60; i++ {
		o, e := Import(root, testOwnedBuild)
		if e != nil {
			t.Fatal(e)
		}
		if _, _, e = o.Acquire(strings.Repeat("b", 64)); e == nil {
			t.Fatal("wrong guest acquired")
		}
		o.Close()
		o.Close()
		original, e := os.ReadFile(filepath.Join(root, "data/seed"))
		if e != nil {
			t.Fatal(e)
		}
		os.WriteFile(filepath.Join(root, "data/seed"), []byte("wrong"), 0600)
		if o, e := Import(root, testOwnedBuild); e == nil {
			o.Close()
			t.Fatal("corruption accepted")
		}
		os.WriteFile(filepath.Join(root, "data/seed"), original, 0600)
	}
	runtime.GC()
	if after := ownedFDCount(t); after != before {
		t.Fatalf("FD count %d -> %d", before, after)
	}
}
func TestInheritedFailureClosesTransferredFD(t *testing.T) {
	root := externalTemplate(t)
	o, e := Import(root, testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	defer o.Close()
	v, release, e := o.Acquire(testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	var fd int
	for _, x := range v {
		if !x.Directory {
			fd, e = syscall.Dup(x.FD)
			if e != nil {
				t.Fatal(e)
			}
		}
	}
	h := Handoff{Manifest: o.manifest, Files: []Descriptor{{Name: "seed", FD: fd}}}
	if received, e := ReceiveInherited(h, strings.Repeat("b", 64)); e == nil {
		received.Close()
		t.Fatal("wrong guest accepted")
	}
	var st syscall.Stat_t
	if e = syscall.Fstat(fd, &st); e != syscall.EBADF {
		t.Fatalf("transferred FD leaked: %v", e)
	}
}
