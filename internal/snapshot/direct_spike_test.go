package snapshot

import (
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"testing/fstest"
)

func directFixture() fstest.MapFS {
	return fstest.MapFS{
		"table":     &fstest.MapFile{Data: []byte("prepared-state"), Mode: 0600},
		"sub/empty": &fstest.MapFile{Data: nil, Mode: 0600},
	}
}

func TestDirectMaterializeOwnership(t *testing.T) {
	root := t.TempDir()
	if e := MaterializeDirect(directFixture(), root, testOwnedBuild); e != nil {
		t.Fatal(e)
	}
	o, e := AdoptCreated(root, testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	defer o.Close()
	if _, e := os.Stat(root); !os.IsNotExist(e) {
		t.Fatalf("path remains: %v", e)
	}
	v, release, e := o.Acquire(testOwnedBuild)
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	for _, file := range v {
		if file.Name != "table" {
			continue
		}
		b := make([]byte, file.Size)
		if _, e := syscall.Pread(file.FD, b, 0); e != nil || string(b) != "prepared-state" {
			t.Fatalf("owned content %q: %v", b, e)
		}
		if _, e := syscall.Pwrite(file.FD, []byte("x"), 0); e != syscall.EBADF {
			t.Fatalf("retained descriptor must be read only: %v", e)
		}
	}
}

func TestDirectAdoptRejectsDamage(t *testing.T) {
	for _, damage := range []string{"content", "size", "extra", "missing", "alias", "guest", "manifest"} {
		t.Run(damage, func(t *testing.T) {
			root := t.TempDir()
			if e := MaterializeDirect(directFixture(), root, testOwnedBuild); e != nil {
				t.Fatal(e)
			}
			name := filepath.Join(root, "data/table")
			build := testOwnedBuild
			var e error
			switch damage {
			case "content":
				e = os.WriteFile(name, []byte("CHANGED!-state"), 0600)
			case "size":
				e = os.Truncate(name, 1)
			case "extra":
				e = os.WriteFile(filepath.Join(root, "data/extra"), nil, 0600)
			case "missing":
				e = os.Remove(name)
			case "alias":
				e = os.Link(name, filepath.Join(t.TempDir(), "alias"))
			case "guest":
				build = strings.Repeat("b", 64)
			case "manifest":
				e = os.WriteFile(filepath.Join(root, "manifest.json"), []byte("{}"), 0600)
			}
			if e != nil {
				t.Fatal(e)
			}
			before := ownedFDCount(t)
			if o, e := AdoptCreated(root, build); e == nil {
				o.Close()
				t.Fatal("damaged output accepted")
			}
			if after := ownedFDCount(t); before != after {
				t.Fatalf("failed adoption leaked descriptors: %d -> %d", before, after)
			}
		})
	}
}

type failedReadFS struct{ fs.FS }

func (f failedReadFS) Open(name string) (fs.File, error) {
	if name == "table" {
		return nil, errors.New("injected read failure")
	}
	return f.FS.Open(name)
}

func TestDirectMaterializeFailures(t *testing.T) {
	for _, fault := range []string{"short-no-error", "write-error", "read-error", "special", "missing-root"} {
		t.Run(fault, func(t *testing.T) {
			root := t.TempDir()
			var source fs.FS = directFixture()
			copyBytes := func(w io.Writer, r io.Reader) (int64, error) { return io.Copy(w, r) }
			switch fault {
			case "short-no-error", "write-error":
				copyBytes = func(w io.Writer, r io.Reader) (int64, error) {
					b := make([]byte, 1)
					n, e := r.Read(b)
					if e == io.EOF {
						return 0, nil
					}
					if e != nil {
						return 0, e
					}
					written, e := w.Write(b[:n])
					if fault == "write-error" {
						e = io.ErrShortWrite
					}
					return int64(written), e
				}
			case "read-error":
				source = failedReadFS{source}
			case "special":
				source = fstest.MapFS{"link": &fstest.MapFile{Mode: fs.ModeSymlink, Data: []byte("outside")}}
			case "missing-root":
				source, _ = fs.Sub(source, "missing")
			}
			before := ownedFDCount(t)
			if e := materializeDirect(source, root, testOwnedBuild, copyBytes); e == nil {
				t.Fatal("failed materialization succeeded")
			}
			if _, e := os.Stat(root); !os.IsNotExist(e) {
				t.Fatalf("partial output remains: %v", e)
			}
			if after := ownedFDCount(t); before != after {
				t.Fatalf("failed materialization leaked descriptors: %d -> %d", before, after)
			}
		})
	}
}

func TestDirectRejectsOccupiedDestination(t *testing.T) {
	root := t.TempDir()
	name := filepath.Join(root, "keep")
	if e := os.WriteFile(name, []byte("original"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := MaterializeDirect(directFixture(), root, testOwnedBuild); e == nil {
		t.Fatal("occupied destination accepted")
	}
	if b, e := os.ReadFile(name); e != nil || string(b) != "original" {
		t.Fatalf("preexisting data changed: %q %v", b, e)
	}
}
