package mariamem

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"mariamem/internal/host"
	stored "mariamem/internal/snapshot"
)

type fakeBackend struct {
	closes   int
	active   int
	closeErr error
	snapshot func(context.Context, string, bool) (bool, error)
}

func (f *fakeBackend) Close(context.Context) error { f.closes++; return f.closeErr }
func (f *fakeBackend) Active() int                 { return f.active }
func (f *fakeBackend) Snapshot(ctx context.Context, p string, r bool) (bool, error) {
	return f.snapshot(ctx, p, r)
}
func testDB(t *testing.T, f *fakeBackend) *Database {
	t.Helper()
	opts, err := (Options{NativeDir: t.TempDir()}).defaults()
	if err != nil {
		t.Fatal(err)
	}
	return &Database{server: f, opts: opts, build: "test-build", temporary: t.TempDir(), info: ConnectionInfo{Host: "127.0.0.1", Port: 12345, User: "root", Database: "test"}}
}
func TestOptions(t *testing.T) {
	if _, err := (Options{}).defaults(); err == nil {
		t.Fatal("missing NativeDir accepted")
	}
	o, err := (Options{NativeDir: "native"}).defaults()
	if err != nil || o.StartupTimeout != 120*time.Second || o.ShutdownTimeout != 30*time.Second || o.QueryTimeout != 30*time.Second {
		t.Fatalf("%+v %v", o, err)
	}
	for _, o := range []Options{{NativeDir: "x", StartupTimeout: -1}, {NativeDir: "x", ShutdownTimeout: -1}, {NativeDir: "x", QueryTimeout: -1}} {
		if _, err := o.defaults(); err == nil {
			t.Fatal("negative timeout accepted")
		}
	}
	o, err = (Options{NativeDir: "x", QueryTimeout: time.Second}).defaults()
	if err != nil || o.QueryTimeout != time.Second {
		t.Fatal("explicit timeout overwritten")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := Start(ctx, Options{NativeDir: "missing"}); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
}
func TestConnection(t *testing.T) {
	db := testDB(t, &fakeBackend{})
	c := db.ConnectionInfo()
	c.Port = 1
	// Interpolation is a text-protocol compatibility setting, not Prepare support.
	if got := db.DSN(); got != "root:@tcp(127.0.0.1:12345)/test?interpolateParams=true" {
		t.Fatal(got)
	}
	db.Close()
	if db.ConnectionInfo().Port != 12345 {
		t.Fatal("metadata mutated")
	}
}
func TestErrors(t *testing.T) {
	for code, want := range map[string]error{"busy": ErrBusy, "transaction_active": ErrTransactionActive, "closed": ErrClosed} {
		original := &host.Rejected{Code: code, Message: "rejected"}
		err := hostError(original, "snapshot_failed", false)
		var detail *HostError
		if !errors.Is(err, want) || !errors.Is(err, original) || !errors.As(err, &detail) || detail.Closed {
			t.Fatal(err)
		}
	}
	if !errors.Is(hostError(context.DeadlineExceeded, "snapshot_failed", true), context.DeadlineExceeded) {
		t.Fatal("lost cause")
	}
}
func TestCloseIdempotent(t *testing.T) {
	original := errors.New("shutdown failed")
	f := &fakeBackend{closeErr: original}
	db := testDB(t, f)
	temp := db.temporary
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if !errors.Is(db.Close(), original) {
				t.Error("lost error")
			}
		}()
	}
	wg.Wait()
	if f.closes != 1 || !db.Closed() {
		t.Fatalf("closes=%d", f.closes)
	}
	if _, err := os.Stat(temp); !os.IsNotExist(err) {
		t.Fatal("temporary directory remains")
	}
	if _, err := db.Snapshot(context.Background(), SnapshotOptions{}); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	if err := db.WaitDisconnected(context.Background()); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
}
func TestZeroValues(t *testing.T) {
	var db Database
	if !db.Closed() {
		t.Fatal("zero DB appears open")
	}
	if _, err := db.Snapshot(context.Background(), SnapshotOptions{}); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	var s Snapshot
	if _, err := s.Fork(context.Background()); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
}
func TestWaitDisconnected(t *testing.T) {
	db := testDB(t, &fakeBackend{})
	if err := db.WaitDisconnected(context.Background()); err != nil {
		t.Fatal(err)
	}
	db.server = &fakeBackend{active: 1}
	ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	defer cancel()
	if err := db.WaitDisconnected(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
}
func TestSnapshotOwnership(t *testing.T) {
	for _, explicit := range []bool{false, true} {
		t.Run(map[bool]string{false: "temporary", true: "explicit"}[explicit], func(t *testing.T) {
			f := &fakeBackend{}
			db := testDB(t, f)
			transfer := t.TempDir()
			if err := os.Mkdir(filepath.Join(transfer, "data"), 0700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(transfer, "data", "seed"), []byte("seed"), 0600); err != nil {
				t.Fatal(err)
			}
			ctx := context.Background()
			f.snapshot = func(got context.Context, path string, rollback bool) (bool, error) {
				if got != ctx {
					t.Error("context replaced")
				}
				if _, ok := got.Deadline(); ok {
					t.Error("implicit snapshot deadline")
				}
				if !rollback {
					t.Error("rollback not forwarded")
				}
				if err := os.Mkdir(path, 0700); err != nil {
					return false, err
				}
				return true, stored.Publish(transfer, path, db.build)
			}
			opts := SnapshotOptions{Rollback: true}
			if explicit {
				opts.Destination = filepath.Join(t.TempDir(), "saved")
			}
			snap, err := db.Snapshot(ctx, opts)
			if err != nil {
				t.Fatal(err)
			}
			if !db.Closed() {
				t.Fatal("source not consumed")
			}
			if _, err := stored.Validate(snap.Path(), db.build); err != nil {
				t.Fatal(err)
			}
			if snap.opts.NativeDir != db.opts.NativeDir {
				t.Fatal("fork options not inherited")
			}
			if err := db.Close(); err != nil || f.closes != 0 {
				t.Fatal("consumed DB shut down twice")
			}
			if err := snap.Close(); err != nil {
				t.Fatal(err)
			}
			if err := snap.Close(); err != nil {
				t.Fatal(err)
			}
			_, err = os.Stat(snap.Path())
			if explicit && err != nil || !explicit && !os.IsNotExist(err) {
				t.Fatalf("ownership: %v", err)
			}
			if _, err := snap.Fork(ctx); !errors.Is(err, ErrClosed) {
				t.Fatal(err)
			}
		})
	}
}
func TestSnapshotFailures(t *testing.T) {
	for _, consumed := range []bool{false, true} {
		t.Run(map[bool]string{false: "rejected", true: "accepted-failure"}[consumed], func(t *testing.T) {
			f := &fakeBackend{}
			db := testDB(t, f)
			var path string
			original := &host.Rejected{Code: "busy", Message: "active query"}
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			f.snapshot = func(got context.Context, p string, _ bool) (bool, error) {
				path = p
				if got != ctx {
					t.Error("caller deadline not forwarded")
				}
				return consumed, original
			}
			_, err := db.Snapshot(ctx, SnapshotOptions{})
			var detail *HostError
			if !errors.As(err, &detail) || detail.Closed != consumed || !errors.Is(err, original) {
				t.Fatal(err)
			}
			if db.Closed() != consumed {
				t.Fatal("wrong source state")
			}
			if _, err := os.Stat(filepath.Dir(path)); !os.IsNotExist(err) {
				t.Fatal("temporary snapshot leaked")
			}
			db.Close()
		})
	}
	// A canceled call does not create a destination or consume the DB.
	db := testDB(t, &fakeBackend{})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := db.Snapshot(ctx, SnapshotOptions{}); !errors.Is(err, context.Canceled) || db.Closed() {
		t.Fatal(err)
	}
}
func TestExplicitRejectionPreservesData(t *testing.T) {
	destination := t.TempDir()
	marker := filepath.Join(destination, "keep")
	os.WriteFile(marker, []byte("original"), 0600)
	f := &fakeBackend{snapshot: func(_ context.Context, path string, _ bool) (bool, error) { return false, os.Mkdir(path, 0700) }}
	db := testDB(t, f)
	if _, err := db.Snapshot(context.Background(), SnapshotOptions{Destination: destination}); err == nil {
		t.Fatal("accepted existing destination")
	}
	b, err := os.ReadFile(marker)
	if err != nil || string(b) != "original" || db.Closed() {
		t.Fatal("existing data lost")
	}
}
func TestLogsBounded(t *testing.T) {
	var db Database
	db.logs.Write([]byte(strings.Repeat("a", 20000)))
	db.logs.Write([]byte("end"))
	if got := db.Logs(); len(got) != 16384 || !strings.HasSuffix(got, "end") {
		t.Fatal("invalid log tail")
	}
}

func TestRuntimeExitCleanup(t *testing.T) {
	f := &fakeBackend{}
	db := testDB(t, f)
	temp := db.temporary
	done := make(chan struct{})
	close(done)
	db.watch(done)
	if !db.Closed() || f.closes != 1 {
		t.Fatal("runtime exit not cleaned up")
	}
	var detail *HostError
	if err := db.Close(); !errors.As(err, &detail) || detail.Code != "runtime_exited" || !detail.Closed {
		t.Fatal(err)
	}
	if _, err := os.Stat(temp); !os.IsNotExist(err) {
		t.Fatal("runtime temp leaked")
	}
	db.watch(done)
	if f.closes != 1 {
		t.Fatal("double cleanup")
	}
}

func TestSuccessfulExportWithInvalidSnapshot(t *testing.T) {
	var destination string
	f := &fakeBackend{snapshot: func(_ context.Context, path string, _ bool) (bool, error) {
		destination = path
		// An acknowledgement alone must not bypass the manifest commit marker.
		return true, os.Mkdir(path, 0700)
	}}
	db := testDB(t, f)
	saved, err := db.Snapshot(context.Background(), SnapshotOptions{})
	if err == nil || saved != nil || !db.Closed() {
		t.Fatal("invalid snapshot accepted")
	}
	if _, err := os.Stat(filepath.Dir(destination)); !os.IsNotExist(err) {
		t.Fatal("invalid snapshot leaked")
	}
}
