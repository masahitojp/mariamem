package mariamem

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// A stopped backend can keep reclaiming resources after its notification.
// The actual guest/transport producer of this boundary belongs to #205.
type stagedCloseBackend struct {
	fakeBackend
	started  chan struct{}
	stopped  chan struct{}
	release  chan struct{}
	calls    atomic.Int32
	disposed atomic.Bool
	fail     atomic.Bool
	result   error
}

func newStagedClose() *stagedCloseBackend {
	return &stagedCloseBackend{started: make(chan struct{}), stopped: make(chan struct{}), release: make(chan struct{})}
}
func (b *stagedCloseBackend) Failure() error {
	if b.fail.Load() {
		return errors.New("injected crash")
	}
	return nil
}
func (b *stagedCloseBackend) DisposalComplete() bool { return b.disposed.Load() }
func (b *stagedCloseBackend) Close(ctx context.Context) error {
	if b.disposed.Load() {
		return b.result
	}
	return b.CloseWithStopped(ctx, func(error) {})
}
func (b *stagedCloseBackend) CloseWithStopped(ctx context.Context, notify func(error)) error {
	if b.calls.Add(1) != 1 {
		panic("duplicate initial shutdown")
	}
	close(b.started)
	<-b.stopped
	notify(nil)
	<-b.release
	b.disposed.Store(true)
	return b.result
}
func closeTestDB(b *stagedCloseBackend) *Database {
	return &Database{server: b, opts: Options{ShutdownTimeout: time.Second}}
}
func closeTestContext(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	t.Cleanup(cancel)
	return ctx
}

func TestCloseOperationSharedAndCancellation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	stopped := make(chan *closeOperation, 1)
	go func() {
		op, err := db.stopForCleanup(ctx)
		if err != nil {
			t.Error(err)
		}
		stopped <- op
	}()
	<-b.started
	if !db.Closed() {
		t.Fatal("still accepting work")
	}
	if _, err := db.DialContext(ctx, "tcp", "ignored"); !errors.Is(err, ErrClosed) {
		t.Fatal("new request accepted", err)
	}
	result := errors.New("saved cleanup result")
	b.result = result
	close(b.stopped)
	op := <-stopped
	if op.Disposed() {
		t.Fatal("disposed before cleanup")
	}
	canceled, cancel := context.WithCancel(ctx)
	cancel()
	if err := op.Wait(canceled); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	results := make(chan error, 12)
	for i := 0; i < 12; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); results <- db.Close() }()
	}
	select {
	case err := <-results:
		t.Fatal("Close returned before result", err)
	default:
	}
	// Normal completion must not be classified as a watch-detected crash.
	done := make(chan struct{})
	close(done)
	db.watch(done)
	if db.Err() != nil {
		t.Fatal("intentional shutdown marked failed", db.Err())
	}
	close(b.release)
	wg.Wait()
	for i := 0; i < 12; i++ {
		if err := <-results; !errors.Is(err, result) {
			t.Fatal(err)
		}
	}
	if err := op.Wait(ctx); !errors.Is(err, result) {
		t.Fatal(err)
	}
	if !op.Disposed() {
		t.Fatal("missing disposal confirmation")
	}
	if !errors.Is(db.Close(), result) || b.calls.Load() != 1 {
		t.Fatal("changed saved result")
	}
}

func TestWatchStartsSameCloseOperation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	b.fail.Store(true)
	done := make(chan struct{})
	close(done)
	watchDone := make(chan struct{})
	go func() { db.watch(done); close(watchDone) }()
	<-b.started
	if !errors.Is(db.Err(), ErrUnusable) {
		t.Fatal("lost crash", db.Err())
	}
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	db.mu.Lock()
	same := db.closing == op
	db.mu.Unlock()
	if !same {
		t.Fatal("different owner")
	}
	close(b.release)
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	<-watchDone
	if !errors.Is(db.Err(), ErrUnusable) || b.calls.Load() != 1 {
		t.Fatal("lost cause or duplicate shutdown")
	}
}

func TestPendingCloseHoldsCapacityWithoutBlockingPool(t *testing.T) {
	for _, cap := range []int{1, 2} {
		t.Run(string(rune('0'+cap)), func(t *testing.T) {
			b := newStagedClose()
			db := closeTestDB(b)
			ctx := closeTestContext(t)
			pool, _ := forklimit.New(cap)
			lease, _ := pool.Acquire(ctx)
			if err := lease.Activate(); err != nil {
				t.Fatal(err)
			}
			db.lease = lease
			close(b.stopped)
			op, err := db.stopForCleanup(ctx)
			if err != nil {
				t.Fatal(err)
			}
			if _, occupied := pool.Usage(); occupied != 1 {
				t.Fatal("premature lease release")
			}
			next, err := pool.TryAcquire(false)
			if cap == 1 && !errors.Is(err, forklimit.ErrFull) {
				t.Fatal("expected occupied capacity", err)
			}
			if cap == 2 {
				if err != nil {
					t.Fatal("normal pending blocked whole pool", err)
				}
				next.Cancel()
			}
			close(b.release)
			if err := op.Wait(ctx); err != nil {
				t.Fatal(err)
			}
			next, err = pool.Acquire(ctx)
			if err != nil {
				t.Fatal(err)
			}
			next.Cancel()
		})
	}
}

func TestLiveJoinsInitialCloseBeforeRetry(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	result := make(chan error, 1)
	go func() { result <- (liveChild{db}).Close() }()
	select {
	case err := <-result:
		t.Fatal("Live did not join", err)
	default:
	}
	close(b.release)
	if err := <-result; err != nil {
		t.Fatal(err)
	}
	if err := op.Wait(ctx); err != nil {
		t.Fatal(err)
	}
	if b.calls.Load() != 1 {
		t.Fatal("duplicate shutdown")
	}
}

func TestStopWaitCancellationKeepsSharedOperation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	waiting, cancel := context.WithCancel(ctx)
	result := make(chan *closeOperation, 1)
	go func() {
		op, err := db.stopForCleanup(waiting)
		if !errors.Is(err, context.Canceled) {
			t.Error(err)
		}
		result <- op
	}()
	<-b.started
	cancel()
	first := <-result
	if first == nil {
		t.Fatal("lost cleanup handle")
	}
	close(b.stopped)
	second, err := db.stopForCleanup(ctx)
	if err != nil || first != second {
		t.Fatal("lost shared operation", err)
	}
	close(b.release)
	if err := second.Wait(ctx); err != nil {
		t.Fatal(err)
	}
}

func TestSnapshotCloseDuringChildCleanup(t *testing.T) {
	s := controlledSnapshot(t, 1)
	ctx := closeTestContext(t)
	lease, err := s.forkLimit().TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	b := newStagedClose()
	db := closeTestDB(b)
	db.lease = lease
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	wait := &capacityWaitContext{Context: ctx, waiting: make(chan struct{})}
	next := make(chan error, 1)
	go func() { _, err := s.Fork(wait); next <- err }()
	select {
	case <-wait.waiting:
	case <-ctx.Done():
		t.Fatal("Fork did not wait", ctx.Err())
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case err := <-next:
		if !errors.Is(err, ErrClosed) {
			t.Fatal(err)
		}
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if op.Disposed() {
		t.Fatal("parent Close claimed child disposal")
	}
	if _, occupied := s.forkLimit().Usage(); occupied != 1 {
		t.Fatal("parent released active child")
	}
	close(b.release)
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	if _, occupied := s.forkLimit().Usage(); occupied != 0 {
		t.Fatal("child lease retained after confirmed disposal")
	}
}

func TestCloseResultSurvivesLateDisposal(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	var allow atomic.Bool
	failure := errors.New("cleanup failed")
	owner := disposal.New(func(context.Context) error {
		if !allow.Load() {
			return failure
		}
		return nil
	})
	b.result = disposal.Retain(nil, failure, owner)
	close(b.stopped)
	close(b.release)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err := op.Wait(ctx); !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if op.Disposed() {
		t.Fatal("failed cleanup reported disposed")
	}
	allow.Store(true)
	if err := disposal.Retry(ctx, b.result); err != nil {
		t.Fatal(err)
	}
	if !op.Disposed() {
		t.Fatal("late successful release not observable")
	}
	if !errors.Is(db.Close(), failure) {
		t.Fatal("late release rewrote saved result")
	}
}
