package mariamem

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/prepared"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
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
					if f.closes != 0 {
						t.Fatal("invalid source was already disposed")
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
			} else if kind == "backing-close-error" {
				if !errors.Is(closeErr, syscall.EBADF) {
					t.Fatal("Close lost backing cleanup failure", closeErr)
				}
			} else if closeErr != nil {
				t.Fatal(closeErr)
			}
			_ = db.Close()
			if f.closes != 1 {
				t.Errorf("backend teardown repeated or missing: %d", f.closes)
			}
		})
	}
}

func TestConsumedCaptureRetainsCleanupAndStableCloseResult(t *testing.T) {
	joined := make(chan struct{})
	var once sync.Once
	t.Cleanup(func() { once.Do(func() { close(joined) }) })
	cause := errors.New("capture consumed before failed join")
	owner := disposal.New(func(ctx context.Context) error { return disposal.Wait(ctx, joined) })
	pending := disposal.Retain(cause, context.DeadlineExceeded, owner)
	f := &fakeBackend{}
	f.snapshot = func(context.Context, bool) (*stored.Owned, bool, error) {
		f.closes++ // Host accepted capture and stopped admission; not yet disposed.
		return nil, true, pending
	}
	db := testDB(t, f)
	baseline, err := db.Snapshot(context.Background(), SnapshotOptions{})
	if baseline != nil || !errors.Is(err, cause) || !db.Closed() {
		t.Fatal(baseline, err)
	}
	if owner.Complete() || !cleanupPending(db.closeErr) {
		t.Fatal("lost pending capture cleanup")
	}
	firstClose := db.Close()
	if firstClose == nil || f.closes != 1 {
		t.Fatal("lost consumed cleanup or closed twice", firstClose, f.closes)
	}
	once.Do(func() { close(joined) })
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if !owner.Complete() || cleanupPending(db.closeErr) {
		t.Fatal("cleanup owner did not complete")
	}
	if db.Close() != firstClose || f.closes != 1 {
		t.Fatal("Close result changed after disposal")
	}
	if !errors.Is(err, cause) {
		t.Fatal("capture failure was rewritten")
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
	return &Database{server: f, opts: opts, build: "test-build", info: ConnectionInfo{Host: "127.0.0.1", Port: 12345, User: "root", Database: "test"}}
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
		if !errors.As(e, &detail) || detail.Closed != consumed ||
			!errors.Is(e, original) || !errors.Is(e, ErrBusy) || db.Closed() != consumed {
			t.Fatal(e)
		}
		if hasHint := strings.Contains(e.Error(), "The source database is still usable"); hasHint != !consumed {
			t.Fatalf("consumed=%v, unexpected recovery guidance in %q", consumed, e)
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

type fakeKeepBackend struct {
	*fakeBackend
	capture func() (*stored.Owned, error)
}

func (f fakeKeepBackend) SnapshotKeep(context.Context) (*stored.Owned, error) {
	return f.capture()
}

func TestSnapshotKeepReportsUnusableOnFailClosed(t *testing.T) {
	backend := &fakeBackend{}
	db := testDB(t, backend)
	defer db.Close()
	unlockErr := errors.New("unlock failed")
	closeErr := errors.New("session closure unconfirmed")
	captures := 0
	var backed *stored.Owned
	db.server = fakeKeepBackend{backend, func() (*stored.Owned, error) {
		captures++
		if captures == 1 {
			return goodBacking(t), unlockErr
		}
		backend.failure = errors.Join(unlockErr, closeErr)
		backed = goodBacking(t)
		return backed, backend.failure
	}}
	opts := SnapshotOptions{KeepDatabase: true}
	ctx := context.Background()

	snap, err := db.Snapshot(ctx, opts)
	var detail *HostError
	if snap != nil || !errors.Is(err, unlockErr) || !errors.As(err, &detail) || detail.Closed || db.Closed() {
		t.Fatalf("unlock failure with successful close: snapshot=%v err=%v", snap, err)
	}
	snap, err = db.Snapshot(ctx, opts)
	if snap != nil || !errors.Is(err, ErrUnusable) || !errors.Is(err, unlockErr) ||
		!errors.Is(err, closeErr) || !errors.As(err, &detail) || detail.Code != "unusable" || !detail.Closed ||
		!db.Closed() || !errors.Is(db.Err(), ErrUnusable) {
		t.Fatalf("double failure: snapshot=%v err=%v db.Err()=%v", snap, err, db.Err())
	}
	if _, release, err := backed.Acquire("test-build"); err == nil {
		release()
		t.Fatal("failed capture left its baseline owned")
	}
	if retry, err := db.Snapshot(ctx, opts); retry != nil || !errors.Is(err, ErrUnusable) || captures != 2 {
		t.Fatalf("snapshot retried against unusable parent: snapshot=%v err=%v captures=%d", retry, err, captures)
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
	db.watch(done)
	if f.closes != 1 {
		t.Fatal("double cleanup")
	}
}

func TestInvalidatedState(t *testing.T) {
	f := &fakeBackend{failure: context.DeadlineExceeded}
	db := testDB(t, f)
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
	checks  *atomic.Int32
}

func (c heldStartupContext) Err() error {
	if c.checks.Add(1) <= 2 {
		return nil
	} // Admission checks precede backing protection.
	c.entered <- struct{}{}
	<-c.release
	return context.Canceled
}

func TestConcurrentForkCloseOwnership(t *testing.T) {
	limit, _ := forklimit.New(2)
	s := &Snapshot{backing: goodBacking(t), opts: Options{NativeDir: "unused"}, limit: limit}
	entered := make(chan struct{}, 2)
	release := make(chan struct{})
	var once sync.Once
	unblock := func() { once.Do(func() { close(release) }) }
	defer unblock()
	results := make(chan error, 2)
	for i := 0; i < 2; i++ {
		ctx := heldStartupContext{Context: context.Background(), entered: entered, release: release, checks: &atomic.Int32{}}
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

func controlledSnapshot(t *testing.T, cap int) *Snapshot {
	t.Helper()
	f := &fakeBackend{snapshot: func(context.Context, bool) (*stored.Owned, bool, error) { return goodBacking(t), true, nil }}
	db := testDB(t, f)
	db.opts.NativeDir = "unused" // Unit startup stops at retired-option validation.
	s, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: cap})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = s.Close() })
	return s
}

type capacityWaitContext struct {
	context.Context
	once    sync.Once
	waiting chan struct{}
}

func (c *capacityWaitContext) Done() <-chan struct{} {
	c.once.Do(func() { close(c.waiting) })
	return c.Context.Done()
}

func TestSnapshotCapacityWaitWakesOnCloseWithActiveChild(t *testing.T) {
	s := controlledSnapshot(t, 1)
	lease, err := s.forkLimit().TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	defer lease.Settle(nil)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	wait := &capacityWaitContext{Context: ctx, waiting: make(chan struct{})}
	result := make(chan error, 1)
	go func() { _, err := s.Fork(wait); result <- err }()
	select {
	case <-wait.waiting:
	case <-ctx.Done():
		t.Fatal("not waiting for capacity")
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case err := <-result:
		if !errors.Is(err, ErrClosed) {
			t.Fatal(err)
		}
	case <-ctx.Done():
		t.Fatal("Close did not wake waiter")
	}
}

func TestSnapshotCapacityProgressAndWaitDeadline(t *testing.T) {
	s := controlledSnapshot(t, 1)
	if s.MaxForks() != 1 {
		t.Fatal(s.MaxForks())
	}
	lease, _ := s.forkLimit().TryAcquire(false)
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	defer lease.Settle(nil)
	ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	_, err := s.Fork(ctx)
	cancel()
	var detail *HostError
	if !errors.Is(err, context.DeadlineExceeded) || !errors.As(err, &detail) || detail.Code != "pool_timeout" || detail.Stage != "fork_wait" || detail.Closed {
		t.Fatal(err)
	}
	if !strings.Contains(err.Error(), "max_forks=1, occupied_slots=1") || !strings.Contains(err.Error(), "close owned children or increase max_forks") {
		t.Fatal("capacity diagnostic missing", err)
	}
	lease.Settle(nil)
	_, err = s.Fork(context.Background())
	if err == nil || !strings.Contains(err.Error(), "legacy NativeDir") {
		t.Fatal("did not progress to startup", err)
	}
	// A startup rejected before allocating resources must return its slot.
	next, e := s.forkLimit().TryAcquire(false)
	if e != nil {
		t.Fatal(e)
	}
	next.Cancel()
}

func TestSnapshotLimitValidationPreservesSource(t *testing.T) {
	f := &fakeBackend{snapshot: func(context.Context, bool) (*stored.Owned, bool, error) {
		t.Fatal("invalid options reached capture")
		return nil, false, nil
	}}
	db := testDB(t, f)
	for _, cap := range []int{-1, int(forklimit.MaxForks) + 1} {
		_, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: cap})
		var detail *HostError
		if !errors.As(err, &detail) || detail.Code != "invalid_options" || detail.Stage != "snapshot_options" || db.Closed() {
			t.Fatal(err)
		}
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestDuplicateReservationCannotReleaseAnotherChild(t *testing.T) {
	s := controlledSnapshot(t, 1)
	lease, _ := s.forkLimit().TryAcquire(false)
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	defer lease.Settle(nil)
	if db, err := s.forkReserved(context.Background(), lease); db != nil || !errors.Is(err, forklimit.ErrLease) {
		t.Fatal(db, err)
	}
	if _, err := s.forkLimit().TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
		t.Fatal("duplicate start released existing child", err)
	}
}

func TestAlreadyCompletedStartupCleanupDoesNotPoisonAdmission(t *testing.T) {
	s := controlledSnapshot(t, 1)
	lease, _ := s.forkLimit().TryAcquire(false)
	_ = lease.Activate()
	owner := disposal.New(func(context.Context) error { return nil })
	if err := owner.Retry(context.Background()); err != nil {
		t.Fatal(err)
	}
	cause := errors.New("startup failed before cleanup was observed")
	err := disposal.Retain(cause, disposal.ErrPending, owner)
	settleStartupLease(lease, err)
	next, e := s.forkLimit().TryAcquire(false)
	if e != nil {
		t.Fatal("already confirmed disposal blocked admission", e)
	}
	next.Cancel()
	if !errors.Is(err, cause) {
		t.Fatal("failure was rewritten")
	}
}

func TestCleanupCauseCannotMasqueradeAsClosedParent(t *testing.T) {
	s := controlledSnapshot(t, 1)
	lease, _ := s.forkLimit().TryAcquire(false)
	_ = lease.Activate()
	lease.Settle(forklimit.ErrClosed)
	_, err := s.Fork(context.Background())
	var detail *HostError
	if !errors.As(err, &detail) || detail.Code != "unusable" || detail.Stage != "fork_admission" || detail.Closed || s.closed {
		t.Fatal(err)
	}
	lease.Settle(nil)
}

func TestConsumedChildCaptureSettlesOnlyItsParentLease(t *testing.T) {
	for _, consumed := range []bool{false, true} {
		t.Run(map[bool]string{false: "preserved", true: "consumed"}[consumed], func(t *testing.T) {
			s := controlledSnapshot(t, 1)
			lease, _ := s.forkLimit().TryAcquire(false)
			if err := lease.Activate(); err != nil {
				t.Fatal(err)
			}
			cause := errors.New("capture rejected")
			f := &fakeBackend{snapshot: func(context.Context, bool) (*stored.Owned, bool, error) { return nil, consumed, cause }}
			child := testDB(t, f)
			child.lease = lease
			_, err := child.Snapshot(context.Background(), SnapshotOptions{MaxForks: 1})
			if !errors.Is(err, cause) {
				t.Fatal(err)
			}
			_, e := s.forkLimit().TryAcquire(false)
			if consumed {
				// An untyped consumed failure cannot certify disposal.
				if !errors.Is(e, forklimit.ErrCleanup) {
					t.Fatal(e)
				}
			} else if !errors.Is(e, forklimit.ErrFull) {
				t.Fatal(e)
			}
			_ = child.Close()
			lease.Settle(nil) // Controlled owner confirms final disposal.
		})
	}
}

func (f *fakeBackend) DialContext(context.Context) (net.Conn, error) {
	return nil, errors.New("fake dial")
}

func TestDialContextPreconditions(t *testing.T) {
	db := &Database{server: &fakeBackend{}, info: ConnectionInfo{Host: "127.0.0.1", Port: 12345}}
	addr := net.JoinHostPort(db.info.Host, strconv.Itoa(db.info.Port))
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if c, e := db.DialContext(ctx, "tcp", addr); c != nil || !errors.Is(e, context.Canceled) {
		t.Fatal(c, e)
	}
	for _, input := range [][2]string{{"unix", addr}, {"tcp", "127.0.0.1:1"}} {
		if c, e := db.DialContext(context.Background(), input[0], input[1]); c != nil || e == nil {
			t.Fatal(c, e)
		}
	}
	for _, network := range []string{"tcp", "tcp4"} {
		_, e := db.DialContext(context.Background(), network, addr)
		var he *HostError
		if !errors.As(e, &he) || he.Code != "dial" {
			t.Fatal(e)
		}
	}
	db.closed = true
	if _, e := db.DialContext(context.Background(), "tcp", addr); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
	db.closed = false
	db.failure = hostError(errors.New("latched"), "unusable", true)
	if _, e := db.DialContext(context.Background(), "tcp", addr); !errors.Is(e, ErrUnusable) {
		t.Fatal(e)
	}
	if !errors.Is(hostError(errors.New("full"), "capacity", false), ErrCapacity) {
		t.Fatal("capacity classification lost")
	}
}

func TestSnapshotFollowerCancelsWhileLeaderInFlight(t *testing.T) {
	for _, tc := range []struct {
		name     string
		consumed bool
		err      error
	}{
		{name: "leader_consumes", consumed: true, err: nil},
		{name: "leader_busy_preserves_db", consumed: false, err: ErrBusy},
	} {
		t.Run(tc.name, func(t *testing.T) {
			entered := make(chan struct{})
			release := make(chan struct{})
			var releaseOnce sync.Once
			t.Cleanup(func() { releaseOnce.Do(func() { close(release) }) })

			var calls atomic.Int32
			f := &fakeBackend{
				snapshot: func(context.Context, bool) (*stored.Owned, bool, error) {
					if calls.Add(1) == 1 {
						close(entered)
						<-release
						if tc.err != nil {
							return nil, tc.consumed, tc.err
						}
						return goodBacking(t), tc.consumed, nil
					}
					t.Errorf("unexpected second backend snapshot call")
					return nil, false, errors.New("unexpected second call")
				},
			}
			db := testDB(t, f)

			type snapResult struct {
				s   *Snapshot
				err error
			}
			leaderCh := make(chan snapResult, 1)
			go func() {
				s, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: 1})
				leaderCh <- snapResult{s: s, err: err}
			}()

			select {
			case <-entered:
			case <-time.After(2 * time.Second):
				t.Fatal("leader did not enter backend snapshot")
			}

			// Follower must return with DeadlineExceeded BEFORE release is closed.
			followerCtx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
			defer cancel()
			followerDone := make(chan error, 1)
			go func() {
				s, err := db.Snapshot(followerCtx, SnapshotOptions{MaxForks: 1})
				if s != nil {
					_ = s.Close()
					followerDone <- errors.New("canceled follower unexpectedly returned snapshot")
					return
				}
				followerDone <- err
			}()

			select {
			case err := <-followerDone:
				if !errors.Is(err, context.DeadlineExceeded) {
					t.Fatalf("follower returned %v, want context.DeadlineExceeded", err)
				}
			case <-time.After(180 * time.Millisecond):
				t.Fatal("follower blocked past deadline while leader was in flight")
			}

			if got := calls.Load(); got != 1 {
				t.Fatalf("backend snapshot calls before leader release = %d, want 1", got)
			}

			releaseOnce.Do(func() { close(release) })
			res := <-leaderCh
			if tc.err != nil {
				if !errors.Is(res.err, tc.err) || res.s != nil {
					t.Fatalf("leader result = (%v, %v), want (nil, %v)", res.s, res.err, tc.err)
				}
				if db.Closed() {
					t.Fatal("source DB closed after non-consuming busy snapshot")
				}
			} else {
				if res.err != nil || res.s == nil {
					t.Fatalf("leader result = (%v, %v), want valid snapshot", res.s, res.err)
				}
				t.Cleanup(func() { _ = res.s.Close() })
				if !db.Closed() {
					t.Fatal("source DB stayed open after consuming snapshot")
				}
			}
			if got := calls.Load(); got != 1 {
				t.Fatalf("total backend snapshot calls = %d, want 1", got)
			}
		})
	}
}

func TestSnapshotKeepFollowerCancelsWhileLeaderInFlight(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	var releaseOnce sync.Once
	t.Cleanup(func() { releaseOnce.Do(func() { close(release) }) })

	var calls atomic.Int32
	backend := &fakeBackend{}
	db := testDB(t, backend)
	db.server = fakeKeepBackend{
		fakeBackend: backend,
		capture: func() (*stored.Owned, error) {
			if calls.Add(1) == 1 {
				close(entered)
				<-release
				return goodBacking(t), nil
			}
			t.Errorf("unexpected second SnapshotKeep call")
			return nil, errors.New("unexpected second call")
		},
	}

	type snapResult struct {
		s   *Snapshot
		err error
	}
	leaderCh := make(chan snapResult, 1)
	go func() {
		s, err := db.Snapshot(context.Background(), SnapshotOptions{KeepDatabase: true, MaxForks: 1})
		leaderCh <- snapResult{s: s, err: err}
	}()

	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("leader did not enter SnapshotKeep")
	}

	followerCtx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	followerDone := make(chan error, 1)
	go func() {
		s, err := db.Snapshot(followerCtx, SnapshotOptions{KeepDatabase: true, MaxForks: 1})
		if s != nil {
			_ = s.Close()
			followerDone <- errors.New("canceled follower unexpectedly returned snapshot")
			return
		}
		followerDone <- err
	}()

	select {
	case err := <-followerDone:
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("follower returned %v, want context.DeadlineExceeded", err)
		}
	case <-time.After(180 * time.Millisecond):
		t.Fatal("KeepDatabase follower blocked past deadline while leader was in flight")
	}

	if got := calls.Load(); got != 1 {
		t.Fatalf("SnapshotKeep calls before leader release = %d, want 1", got)
	}

	releaseOnce.Do(func() { close(release) })
	res := <-leaderCh
	if res.err != nil || res.s == nil {
		t.Fatalf("leader result = (%v, %v), want valid snapshot", res.s, res.err)
	}
	t.Cleanup(func() { _ = res.s.Close() })
	if db.Closed() {
		t.Fatal("source DB closed after KeepDatabase snapshot")
	}
	if got := calls.Load(); got != 1 {
		t.Fatalf("total SnapshotKeep calls = %d, want 1", got)
	}
}

func TestSnapshotWaitingFollowerProceedsAfterLeaderBusy(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	var releaseOnce sync.Once
	t.Cleanup(func() { releaseOnce.Do(func() { close(release) }) })

	var calls atomic.Int32
	f := &fakeBackend{
		snapshot: func(context.Context, bool) (*stored.Owned, bool, error) {
			switch calls.Add(1) {
			case 1:
				close(entered)
				<-release
				return nil, false, ErrBusy
			case 2:
				return goodBacking(t), true, nil
			default:
				t.Errorf("unexpected extra backend snapshot call")
				return nil, false, errors.New("unexpected extra call")
			}
		},
	}
	db := testDB(t, f)

	type snapResult struct {
		s   *Snapshot
		err error
	}
	leaderCh := make(chan snapResult, 1)
	go func() {
		s, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: 1})
		leaderCh <- snapResult{s: s, err: err}
	}()

	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("leader did not enter backend snapshot")
	}

	liveCh := make(chan snapResult, 1)
	go func() {
		s, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: 1})
		liveCh <- snapResult{s: s, err: err}
	}()

	canceledCtx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	canceledDone := make(chan error, 1)
	go func() {
		s, err := db.Snapshot(canceledCtx, SnapshotOptions{MaxForks: 1})
		if s != nil {
			_ = s.Close()
			canceledDone <- errors.New("canceled follower unexpectedly returned snapshot")
			return
		}
		canceledDone <- err
	}()

	select {
	case err := <-canceledDone:
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("canceled follower returned %v, want context.DeadlineExceeded", err)
		}
	case <-time.After(180 * time.Millisecond):
		t.Fatal("canceled follower blocked past deadline while leader was in flight")
	}

	select {
	case res := <-liveCh:
		if res.s != nil {
			_ = res.s.Close()
		}
		t.Fatalf("live follower returned before leader released: (%v, %v)", res.s, res.err)
	default:
	}
	if got := calls.Load(); got != 1 {
		t.Fatalf("backend snapshot calls before leader release = %d, want 1", got)
	}

	releaseOnce.Do(func() { close(release) })

	leaderRes := <-leaderCh
	if !errors.Is(leaderRes.err, ErrBusy) || leaderRes.s != nil {
		t.Fatalf("leader result = (%v, %v), want (nil, ErrBusy)", leaderRes.s, leaderRes.err)
	}

	var liveRes snapResult
	select {
	case liveRes = <-liveCh:
	case <-time.After(2 * time.Second):
		t.Fatal("live follower did not proceed after non-consuming leader finished")
	}
	if liveRes.err != nil || liveRes.s == nil {
		t.Fatalf("live follower result = (%v, %v), want valid snapshot", liveRes.s, liveRes.err)
	}
	t.Cleanup(func() { _ = liveRes.s.Close() })
	if !db.Closed() {
		t.Fatal("source DB stayed open after live follower consumed snapshot")
	}
	if got := calls.Load(); got != 2 {
		t.Fatalf("total backend snapshot calls = %d, want 2", got)
	}
}

func TestCloseDuringInFlightSnapshotSerializesBackendClose(t *testing.T) {
	for _, consumed := range []bool{false, true} {
		t.Run(map[bool]string{false: "non_consuming", true: "consuming"}[consumed], func(t *testing.T) {
			entered := make(chan struct{})
			release := make(chan struct{})
			var releaseOnce sync.Once
			t.Cleanup(func() { releaseOnce.Do(func() { close(release) }) })

			var inSnapshot atomic.Bool
			var closeDuringSnapshot atomic.Bool
			f := &fakeBackend{
				snapshot: func(context.Context, bool) (*stored.Owned, bool, error) {
					inSnapshot.Store(true)
					close(entered)
					<-release
					inSnapshot.Store(false)
					if consumed {
						return goodBacking(t), true, nil
					}
					return nil, false, ErrBusy
				},
			}
			wrapped := &closeCheckBackend{
				fakeBackend: f,
				onClose: func() {
					if inSnapshot.Load() {
						closeDuringSnapshot.Store(true)
					}
				},
			}
			db := &Database{server: wrapped, opts: Options{ShutdownTimeout: time.Second}}
			t.Cleanup(func() { _ = db.Close() })

			leaderDone := make(chan error, 1)
			go func() {
				s, err := db.Snapshot(context.Background(), SnapshotOptions{MaxForks: 1})
				if s != nil {
					_ = s.Close()
				}
				leaderDone <- err
			}()
			<-entered

			closeDone := make(chan error, 1)
			go func() {
				closeDone <- db.Close()
			}()
			time.Sleep(20 * time.Millisecond)
			if closeDuringSnapshot.Load() {
				t.Fatal("backend Close ran concurrently with in-flight Snapshot")
			}

			releaseOnce.Do(func() { close(release) })
			<-leaderDone
			if err := <-closeDone; err != nil {
				t.Fatalf("Close returned %v", err)
			}
			if closeDuringSnapshot.Load() {
				t.Fatal("backend Close ran concurrently with in-flight Snapshot")
			}
			wantCloses := 1
			if consumed {
				wantCloses = 0
			}
			if wrapped.closes != wantCloses {
				t.Fatalf("backend closes = %d, want %d", wrapped.closes, wantCloses)
			}
		})
	}
}

type closeCheckBackend struct {
	*fakeBackend
	onClose func()
}

func (b *closeCheckBackend) Close(ctx context.Context) error {
	if b.onClose != nil {
		b.onClose()
	}
	return b.fakeBackend.Close(ctx)
}

func TestSnapshotFailureRetainsParentLeaseUntilDisposal(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	root, err := Start(ctx, Options{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = root.Close() })
	parent, err := root.Snapshot(ctx, SnapshotOptions{MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = parent.Close() })
	pool := parent.forkLimit()
	lease, err := pool.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}

	guestDone := make(chan struct{})
	releaseGuest := sync.OnceFunc(func() { close(guestDone) })
	defer releaseGuest()
	owner := disposal.New(func(ctx context.Context) error { return disposal.Wait(ctx, guestDone) })
	cause := errors.New("snapshot guest failed")
	child := testDB(t, &fakeBackend{snapshot: func(context.Context, bool) (*stored.Owned, bool, error) {
		return nil, true, disposal.Retain(cause, disposal.ErrPending, owner)
	}})
	child.lease = lease

	_, err = child.Snapshot(context.Background(), SnapshotOptions{})
	var detail *HostError
	if !errors.Is(err, cause) || !errors.As(err, &detail) || !detail.Closed || !child.Closed() {
		t.Fatalf("expected a consuming error that preserves the cause: %v", err)
	}
	if _, err := pool.TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
		t.Fatalf("expected pending cleanup to occupy the only slot: %v", err)
	}

	releaseGuest()
	next, err := parent.Fork(ctx)
	if err != nil {
		t.Fatalf("ordinary Fork could not reuse the parent after cleanup: %v", err)
	}
	if err := next.Close(); err != nil {
		t.Fatal(err)
	}
}
