package mariamem

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/prepared"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/host"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// The ownership contract is tested with a controlled backend and real unlinked
// backing, not a claim to reproduce every generated-engine I/O failure.
func physicalBacking(t *testing.T) (*stored.Owned, int) {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "data"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "data", "seed"), []byte("seed"), 0600); err != nil {
		t.Fatal(err)
	}
	entries, err := stored.Inventory(filepath.Join(root, "data"))
	if err != nil {
		t.Fatal(err)
	}
	manifest := stored.Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: "test-build", Storage: "memory", Entries: entries}
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(root, "manifest.json"), data, 0600); err != nil {
		t.Fatal(err)
	}
	owned, err := stored.AdoptCreated(root, "test-build")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = owned.Close() })
	views, release, err := owned.Acquire("test-build")
	if err != nil {
		t.Fatal(err)
	}
	fd := -1
	for _, v := range views {
		if !v.Directory {
			fd = v.FD
		}
	}
	release()
	if fd < 0 {
		t.Fatal("missing physical backing descriptor")
	}
	return owned, fd
}

func TestSnapshotPhysicalOwnership(t *testing.T) {
	for _, kind := range []string{"preserved", "consumed", "success", "backing-close-error", "invalid", "source-close-error"} {
		t.Run(kind, func(t *testing.T) {
			f := &fakeBackend{}
			db := testDB(t, f)
			temp := db.temporary
			owned, fd := physicalBacking(t)
			original := errors.New("injected capture failure")
			consumed := kind == "consumed" || kind == "success" || kind == "backing-close-error"
			if kind == "invalid" {
				f.failure = original
			}
			if kind == "source-close-error" {
				f.closeErr = syscall.EIO
			}
			f.snapshot = func(context.Context, bool) (*stored.Owned, bool, error) {
				if consumed {
					_ = f.Close(context.Background())
				}
				if kind == "backing-close-error" {
					if err := syscall.Close(fd); err != nil {
						t.Fatal(err)
					}
				}
				if kind == "success" {
					return owned, true, nil
				}
				return owned, consumed, original
			}
			snap, err := db.Snapshot(context.Background(), SnapshotOptions{})
			if kind == "success" {
				if err != nil || snap == nil {
					t.Fatal(err)
				}
				var st syscall.Stat_t
				if err = syscall.Fstat(fd, &st); err != nil {
					t.Fatal("baseline released before its owner", err)
				}
				if err = snap.Close(); err != nil {
					t.Fatal(err)
				}
				if err = snap.Close(); err != nil {
					t.Fatal(err)
				}
			} else {
				if snap != nil || !errors.Is(err, original) {
					t.Fatal("capture cause/admission", err)
				}
				if kind == "backing-close-error" && !errors.Is(err, syscall.EBADF) {
					t.Fatal("backing cleanup cause lost", err)
				}
				if kind == "invalid" {
					if !db.Closed() {
						t.Fatal("invalid source must report unusable")
					}
					if _, e := os.Stat(temp); e != nil {
						t.Fatal("invalid source was already disposed", e)
					}
					_ = owned.Close() // Capture was never entered; this is the test's unused backing.
				} else if db.Closed() != consumed {
					t.Fatal("wrong consumed state")
				}
			}
			var st syscall.Stat_t
			if e := syscall.Fstat(fd, &st); e != syscall.EBADF {
				t.Errorf("partial backing descriptor retained: %v", e)
			}
			if !consumed && f.closes != 0 {
				t.Fatal("preserved source torn down before helper cleanup")
			}
			closeErr := db.Close()
			if kind == "source-close-error" {
				if !errors.Is(closeErr, syscall.EIO) {
					t.Fatal("source cleanup cause lost", closeErr)
				}
			} else if closeErr != nil {
				t.Fatal(closeErr)
			}
			_ = db.Close()
			if f.closes != 1 {
				t.Errorf("backend teardown repeated or missing: %d", f.closes)
			}
			if _, e := os.Stat(temp); !os.IsNotExist(e) {
				t.Errorf("source temporary directory retained: %v", e)
			}
		})
	}
}

type fakeBackend struct {
	closes   int
	active   int
	closeErr error
	failure  error
	snapshot func(context.Context, bool) (*stored.Owned, bool, error)
}

func (f *fakeBackend) Close(context.Context) error { f.closes++; return f.closeErr }
func (f *fakeBackend) Active() int                 { return f.active }
func (f *fakeBackend) Capacity() int               { return 16 }
func (f *fakeBackend) Failure() error              { return f.failure }
func (f *fakeBackend) SnapshotHeap(ctx context.Context, r bool) (*stored.Owned, bool, error) {
	return f.snapshot(ctx, r)
}
func goodBacking(t *testing.T) *stored.Owned {
	t.Helper()
	data := make([]byte, prepared.BlockSize)
	copy(data, "seed")
	block, e := prepared.TakeBlock(data, 4)
	if e != nil {
		t.Fatal(e)
	}
	digest := fmt.Sprintf("%x", sha256.Sum256(data[:4]))
	f, e := prepared.NewHeapFile(4, []prepared.Block{block}, digest)
	if e != nil {
		t.Fatal(e)
	}
	h, e := prepared.NewHeap("test-build", []string{"."}, map[string]*prepared.HeapFile{"seed": f})
	if e != nil {
		t.Fatal(e)
	}
	o, e := stored.OwnHeap(h, "test-build")
	if e != nil {
		t.Fatal(e)
	}
	return o
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
	if _, err := (Options{}).defaults(); err != nil {
		t.Fatal(err)
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
	if err := db.Err(); err != nil {
		t.Fatalf("clean Close invalidated DB: %v", err)
	}
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
	f := &fakeBackend{}
	db := testDB(t, f)
	ctx := context.Background()
	f.snapshot = func(got context.Context, r bool) (*stored.Owned, bool, error) {
		if got != ctx || !r {
			t.Error("context/rollback not forwarded")
		}
		if _, ok := got.Deadline(); ok {
			t.Error("implicit deadline")
		}
		return goodBacking(t), true, nil
	}
	snap, e := db.Snapshot(ctx, SnapshotOptions{Rollback: true})
	if e != nil {
		t.Fatal(e)
	}
	if !db.Closed() {
		t.Fatal("source not consumed")
	}
	entries, release, e := snap.backing.Acquire(db.build)
	if e != nil {
		t.Fatal(e)
	}
	if len(entries) != 1 || entries[0].Heap == nil {
		t.Fatal("not owned heap")
	}
	release()
	if snap.opts != db.opts {
		t.Fatal("options changed")
	}
	if e = db.Close(); e != nil || f.closes != 0 {
		t.Fatal("double shutdown")
	}
	if e = snap.Close(); e != nil {
		t.Fatal(e)
	}
	if e = snap.Close(); e != nil {
		t.Fatal(e)
	}
	if _, e = snap.Fork(ctx); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
}
func TestSnapshotFailures(t *testing.T) {
	for _, consumed := range []bool{false, true} {
		f := &fakeBackend{}
		db := testDB(t, f)
		original := &host.Rejected{Code: "busy", Message: "active query"}
		ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
		f.snapshot = func(got context.Context, _ bool) (*stored.Owned, bool, error) {
			if got != ctx {
				t.Error("context changed")
			}
			return nil, consumed, original
		}
		_, e := db.Snapshot(ctx, SnapshotOptions{})
		var detail *HostError
		if !errors.As(e, &detail) || detail.Closed != consumed || !errors.Is(e, original) || db.Closed() != consumed {
			t.Fatal(e)
		}
		db.Close()
		cancel()
	}
	db := testDB(t, &fakeBackend{})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, e := db.Snapshot(ctx, SnapshotOptions{}); !errors.Is(e, context.Canceled) || db.Closed() {
		t.Fatal(e)
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
	f := &fakeBackend{failure: errors.New("guest exited")}
	db := testDB(t, f)
	temp := db.temporary
	done := make(chan struct{})
	close(done)
	db.watch(done)
	if !db.Closed() || f.closes != 1 {
		t.Fatal("runtime exit not cleaned up")
	}
	var detail *HostError
	if err := db.Err(); !errors.As(err, &detail) || detail.Code != "unusable" || !detail.Closed || !errors.Is(err, ErrUnusable) {
		t.Fatal(err)
	}
	if err := db.Close(); err != nil {
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

func TestInvalidatedState(t *testing.T) {
	f := &fakeBackend{failure: context.DeadlineExceeded}
	db := testDB(t, f)
	temp := db.temporary
	if !db.Closed() || !errors.Is(db.Err(), ErrUnusable) || !errors.Is(db.Err(), context.DeadlineExceeded) {
		t.Fatalf("invalid state: closed=%v err=%v", db.Closed(), db.Err())
	}
	if _, err := db.Snapshot(context.Background(), SnapshotOptions{}); !errors.Is(err, ErrUnusable) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("snapshot after invalidation: %v", err)
	}
	if err := db.WaitDisconnected(context.Background()); !errors.Is(err, ErrUnusable) {
		t.Fatalf("wait after invalidation: %v", err)
	}
	done := make(chan struct{})
	close(done)
	db.watch(done)
	if err := db.Close(); err != nil {
		t.Fatalf("close after invalidation: %v", err)
	}
	if f.closes != 1 {
		t.Fatalf("cleanup calls: %d", f.closes)
	}
	if _, err := os.Stat(temp); !os.IsNotExist(err) {
		t.Fatalf("temporary directory remains: %v", err)
	}
}

func TestSuccessfulCaptureWithoutOwnedSnapshot(t *testing.T) {
	f := &fakeBackend{snapshot: func(context.Context, bool) (*stored.Owned, bool, error) { return nil, true, nil }}
	db := testDB(t, f)
	saved, e := db.Snapshot(context.Background(), SnapshotOptions{})
	if e == nil || saved != nil || !db.Closed() {
		t.Fatal("unowned acknowledgement accepted")
	}
}

// Hold startup at its initial context check, after Fork has acquired its lock.
// Returning cancellation after release avoids starting a runtime in unit tests.
type heldStartupContext struct {
	context.Context
	entered chan<- struct{}
	release <-chan struct{}
}

func (c heldStartupContext) Err() error {
	c.entered <- struct{}{}
	<-c.release
	return context.Canceled
}

func TestConcurrentForkCloseOwnership(t *testing.T) {
	s := &Snapshot{backing: goodBacking(t), opts: Options{NativeDir: "unused"}}
	entered := make(chan struct{}, 2)
	release := make(chan struct{})
	var once sync.Once
	unblock := func() { once.Do(func() { close(release) }) }
	defer unblock()
	ctx := heldStartupContext{Context: context.Background(), entered: entered, release: release}
	results := make(chan error, 2)
	for i := 0; i < 2; i++ {
		go func() { _, e := s.Fork(ctx); results <- e }()
	}
	for i := 0; i < 2; i++ {
		select {
		case <-entered:
		case <-time.After(5 * time.Second):
			t.Fatal("Fork serialized")
		}
	}
	closed := make(chan error, 1)
	go func() { closed <- s.Close() }()
	deadline := time.Now().Add(5 * time.Second)
	for s.mu.TryRLock() {
		s.mu.RUnlock()
		if time.Now().After(deadline) {
			t.Fatal("Close not queued")
		}
		time.Sleep(time.Millisecond)
	}
	late := make(chan error, 1)
	go func() { _, e := s.Fork(context.Background()); late <- e }()
	select {
	case e := <-closed:
		t.Fatalf("Close during startup: %v", e)
	default:
	}
	unblock()
	for i := 0; i < 2; i++ {
		if e := <-results; !errors.Is(e, context.Canceled) {
			t.Fatal(e)
		}
	}
	if e := <-closed; e != nil {
		t.Fatal(e)
	}
	if e := <-late; !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
	if _, _, e := s.backing.Acquire("test-build"); e == nil {
		t.Fatal("closed backing available")
	}
}

func TestSequentialForkReleasesReadLock(t *testing.T) {
	s := &Snapshot{backing: &stored.Owned{}, opts: Options{NativeDir: "unused"}}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	for i := 0; i < 2; i++ {
		if _, err := s.Fork(ctx); !errors.Is(err, context.Canceled) {
			t.Fatal(err)
		}
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestStartupErrorBoundaryAndLifecycleCause(t *testing.T) {
	cause := diagnostic.Wrap("guest_connection", "guest_ready", context.DeadlineExceeded)
	err := hostError(cause, "start", true)
	var detail *HostError
	if !errors.As(err, &detail) || detail.Code != "guest_connection" || detail.Stage != "guest_ready" || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("%v", err)
	}
	err = hostError(errors.Join(ErrUnusable, cause), "unusable", true)
	if !errors.As(err, &detail) || detail.Code != "unusable" || !errors.Is(err, ErrUnusable) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("%v", err)
	}
}

func TestPublicForkTimingRetainsPreparationFailureAndNestedScopes(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	traces := map[string]timing.Trace{}
	ctx := timing.WithRecorder(context.Background(), func(trace timing.Trace) { traces[trace.Operation] = trace })
	snapshot := &Snapshot{backing: &stored.Owned{}, opts: Options{NativeDir: t.TempDir()}}
	db, err := snapshot.Fork(ctx)
	if err == nil || db != nil {
		t.Fatal("missing native input unexpectedly started", db, err)
	}
	if len(traces) != 2 {
		t.Fatal(traces)
	}
	api := traces["api_startup"].Events
	fork := traces["fork"].Events
	if len(api) != 3 || api[1].Name != "options_ready" || api[2].Name != "end" {
		t.Fatal(api)
	}
	if len(fork) != 4 || fork[1].Name != "snapshot_handle_ready" || fork[2].Name != "startup_returned" {
		t.Fatal(fork)
	}
	if snapshot.closed {
		t.Fatal("diagnostics consumed failed fork source")
	}
}

func TestRetiredRuntimeOverrides(t *testing.T) {
	for _, tc := range []struct{ dir, native, kind string }{
		{"bundle", "", ""}, {"", "bundle", ""}, {"", "", "wasmer"}, {"", "", "unknown"},
	} {
		t.Setenv("MARIAMEM_NATIVE_DIR", tc.native)
		t.Setenv("MARIAMEM_RUNTIME", tc.kind)
		_, err := Start(context.Background(), Options{NativeDir: tc.dir})
		if err == nil || !strings.Contains(err.Error(), "generated-Go") {
			t.Fatal(err)
		}
	}
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	for _, kind := range []string{"", "generated-go"} {
		t.Setenv("MARIAMEM_RUNTIME", kind)
		if err := rejectLegacyRuntime(""); err != nil {
			t.Fatal(err)
		}
	}
}
