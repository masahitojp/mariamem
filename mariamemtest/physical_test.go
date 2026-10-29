package mariamemtest

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"testing"

	"github.com/masahitojp/mariamem"
)

// Interface-level fault controls own real OS resources. Root Snapshot tests
// separately verify the concrete Database/Owned boundary, including partial FDs.
type physicalDB struct {
	*fakeDB
	file      *os.File
	temp      string
	once      sync.Once
	disposals int
	cleanup   error
}

func (d *physicalDB) dispose() {
	d.once.Do(func() { d.disposals++; d.cleanup = errors.Join(d.file.Close(), os.RemoveAll(d.temp), d.closeErr) })
}
func (d *physicalDB) Close() error { d.dispose(); return d.cleanup }
func TestFixturePhysicalCleanup(t *testing.T) {
	for _, kind := range []string{"preserved", "consumed", "partial-baseline", "invalid", "cleanup-error"} {
		t.Run(kind, func(t *testing.T) {
			deps, fake, b, j := environment()
			temp := filepath.Join(t.TempDir(), "source")
			if err := os.Mkdir(temp, 0700); err != nil {
				t.Fatal(err)
			}
			file, err := os.Create(filepath.Join(temp, "backend"))
			if err != nil {
				t.Fatal(err)
			}
			fd := int(file.Fd())
			d := &physicalDB{fakeDB: fake, file: file, temp: temp}
			t.Cleanup(func() { d.dispose() })
			original := errors.New("capture failure")
			if kind == "cleanup-error" {
				d.closeErr = syscall.EIO
			}
			backing, err := os.Create(filepath.Join(t.TempDir(), "baseline"))
			if err != nil {
				t.Fatal(err)
			}
			if err = os.Remove(backing.Name()); err != nil {
				t.Fatal(err)
			}
			backingFD := int(backing.Fd())
			t.Cleanup(func() { _ = backing.Close() })
			base := &physicalBase{fakeBase: b, file: backing}
			deps.start = func(context.Context, mariamem.Options) (database, error) { return d, nil }
			d.captureFn = func(context.Context) (baseline, error) {
				if kind == "consumed" {
					d.dispose()
				}
				if kind == "invalid" {
					return nil, &mariamem.HostError{Code: "unusable", Closed: true, Err: original}
				}
				if kind == "partial-baseline" {
					return base, original
				}
				return nil, original
			}
			fixture, err := newFixture(t.Context(), Options{}, deps)
			if fixture != nil || !errors.Is(err, original) {
				t.Fatal("failed setup admitted fixture or lost cause", err)
			}
			if kind == "cleanup-error" && !errors.Is(err, syscall.EIO) {
				t.Fatal("cleanup cause lost", err)
			}
			if d.disposals != 1 {
				t.Errorf("source owner not finalized once: %d", d.disposals)
			}
			var st syscall.Stat_t
			if e := syscall.Fstat(fd, &st); e != syscall.EBADF {
				t.Errorf("source owner descriptor retained: %v", e)
			}
			if _, e := os.Stat(temp); !os.IsNotExist(e) {
				t.Errorf("source owner temporary directory retained: %v", e)
			}
			if j.count("source.pool.close") != 1 {
				t.Fatal("preparation pool not closed exactly once", j.text())
			}
			if kind == "partial-baseline" {
				if base.closes != 1 {
					t.Errorf("partial baseline close count: %d", base.closes)
				}
				if e := syscall.Fstat(backingFD, &st); e != syscall.EBADF {
					t.Errorf("partial baseline descriptor retained: %v", e)
				}
			}
		})
	}
}

type physicalBase struct {
	*fakeBase
	file   *os.File
	closes int
}

func (b *physicalBase) Close() error { b.closes++; return b.file.Close() }

func TestCaptureFailureDoesNotClaimInternalCleanupKnown(t *testing.T) {
	deps, d, _, _ := environment()
	primary, cleanup := errors.New("capture cause"), errors.New("internal backing release failed")
	d.captureFn = func(context.Context) (baseline, error) {
		_ = d.Close()
		return nil, &mariamem.HostError{Code: "snapshot_failed", Closed: true, Err: errors.Join(primary, cleanup)}
	}
	f, err := newFixture(t.Context(), Options{}, deps)
	var detail *Error
	if f != nil || !errors.Is(err, primary) || !errors.Is(err, cleanup) || !errors.As(err, &detail) {
		t.Fatal(err)
	}
	if detail.CleanupState == "completed" {
		t.Fatal("capture-internal cleanup was asserted complete without evidence")
	}
}
