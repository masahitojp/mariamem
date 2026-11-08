package control

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

type debtService struct {
	host.Service
	cause error
}

func (s *debtService) SnapshotHeap(context.Context, bool) (*snapshot.Owned, bool, error) {
	return nil, true, s.cause
}
func (s *debtService) CaptureDebt() error     { return s.cause }
func (s *debtService) DisposalComplete() bool { return true }
func TestNativeCaptureDebtReachesControlParent(t *testing.T) {
	parent := handoffBaseline(t)
	lease, e := parent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal(e)
	}
	if e = lease.Activate(); e != nil {
		t.Fatal(e)
	}
	cause := errors.New("native captured-root debt")
	d := &db{gate: make(chan struct{}, 1), server: &debtService{cause: cause}, shutdown: time.Second, lease: lease}
	m := newManager()
	m.dbs[1] = d
	if _, e = m.call(context.Background(), Request{Op: "snapshot", Handle: 1}); !errors.Is(e, cause) {
		t.Fatal(e)
	}
	if !errors.Is(d.captureDebt, cause) {
		t.Fatal("backend debt lost")
	}
	if _, e = parent.limit.TryAcquire(false); !errors.Is(e, forklimit.ErrCleanup) {
		t.Fatalf("parent lease forgiven: %v", e)
	}
}

// This is control/typed-owner unit evidence with a synthetic service, not a
// native guest fault. Real-worker public fixtures live in the Issue130 overlay.
type lateNativeService struct {
	host.Service
	owner *disposal.Owner
	cause error
}

func (s *lateNativeService) Close(ctx context.Context) error {
	if e := s.owner.Retry(ctx); e != nil {
		return disposal.Retain(s.cause, e, s.owner)
	}
	return s.cause
}
func (s *lateNativeService) Failure() error         { return s.cause }
func (s *lateNativeService) DisposalComplete() bool { return s.owner.Complete() }

func TestNativeControlLateJoinLogFailurePreservesResultAndLease(t *testing.T) {
	parent := handoffBaseline(t)
	independent := handoffBaseline(t)
	lease, e := parent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal(e)
	}
	if e = lease.Activate(); e != nil {
		t.Fatal(e)
	}
	joined := make(chan struct{})
	var once sync.Once
	release := func() { once.Do(func() { close(joined) }) }
	t.Cleanup(release)
	cause := errors.New("original native worker failure (unit service)")
	s := &lateNativeService{owner: disposal.New(func(ctx context.Context) error { return disposal.Wait(ctx, joined) }), cause: cause}
	// A nonempty directory makes os.Remove fail on both supported hosts without
	// relying on permissions (which privileged test runners could bypass).
	logPath := filepath.Join(t.TempDir(), "owned-log")
	if e = os.Mkdir(logPath, 0700); e != nil {
		t.Fatal(e)
	}
	obstruction := filepath.Join(logPath, "held")
	if e = os.WriteFile(obstruction, []byte("log removal fault"), 0600); e != nil {
		t.Fatal(e)
	}
	d := &db{gate: make(chan struct{}, 1), server: s, shutdown: time.Millisecond, lease: lease, logPath: logPath, ownedLog: true}
	m := newManager()
	m.dbs[1] = d
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if _, e = m.call(ctx, Request{Op: "status", Handle: 1}); !errors.Is(e, cause) {
		t.Fatal("status lost first cause", e)
	}
	first := d.close()
	if !errors.Is(first, cause) || !errors.Is(first, context.DeadlineExceeded) || len(disposal.Owners(first)) == 0 {
		t.Fatal("typed owner/cause lost", first)
	}
	if d.disposed() {
		t.Fatal("disposed before execution join")
	}
	if _, e = os.Stat(obstruction); e != nil {
		t.Fatal("log removed before join", e)
	}
	if _, occupied := parent.limit.Usage(); occupied != 1 {
		t.Fatal("parent lease released before join", occupied)
	}
	unrelated, e := independent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal("unrelated parent blocked", e)
	}
	unrelated.Cancel()
	release()
	if e = disposal.Retry(ctx, first); e == nil {
		t.Fatal("log removal failure was hidden")
	}
	if !s.DisposalComplete() || d.disposed() {
		t.Fatal("execution/log disposal were conflated")
	}
	if _, occupied := parent.limit.Usage(); occupied != 1 {
		t.Fatal("lease released before log cleanup", occupied)
	}
	if e = os.Remove(obstruction); e != nil {
		t.Fatal(e)
	}
	if e = d.retryCleanup(ctx); !errors.Is(e, cause) {
		t.Fatal("cleanup retry lost operation cause", e)
	}
	if !d.disposed() {
		t.Fatal("late cleanup incomplete")
	}
	if _, e = os.Stat(logPath); !os.IsNotExist(e) {
		t.Fatal("late log remains", e)
	}
	if d.close() != first || !errors.Is(first, cause) {
		t.Fatal("stored Close result changed")
	}
	if _, occupied := parent.limit.Usage(); occupied != 0 {
		t.Fatal("ordinary cleanup did not retire lease", occupied)
	}
}

func (s *debtService) Close(context.Context) error { return nil }

func TestNativeControlPermanentDebtIsolatedAfterPhysicalCleanup(t *testing.T) {
	parent := handoffBaseline(t)
	var e error
	parent.limit, e = forklimit.New(2)
	if e != nil {
		t.Fatal(e)
	}
	debtLease, e := parent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal(e)
	}
	if e = debtLease.Activate(); e != nil {
		t.Fatal(e)
	}
	sibling, e := parent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal(e)
	}
	if e = sibling.Activate(); e != nil {
		t.Fatal(e)
	}
	independent := handoffBaseline(t)
	cause := errors.New("post-capture ownership fault (unit service)")
	d := &db{gate: make(chan struct{}, 1), server: &debtService{cause: cause}, shutdown: time.Second, lease: debtLease}
	m := newManager()
	m.dbs[1] = d
	result, operation := m.call(context.Background(), Request{Op: "snapshot", Handle: 1})
	if !errors.Is(operation, cause) || result["closed"] != true || result["disposed"] != false || result["cleanup_handle"] != uint64(1) {
		t.Fatal("consumed permanent debt lost", result, operation)
	}
	stored := d.close()
	if e = d.retryCleanup(context.Background()); !errors.Is(e, cause) {
		t.Fatal("cleanup forgave capture debt", e)
	}
	if !d.server.DisposalComplete() || d.disposed() {
		t.Fatal("physical join erased permanent debt")
	}
	if d.close() != stored || !errors.Is(operation, cause) {
		t.Fatal("stored results changed")
	}
	sibling.Settle(nil)
	if _, occupied := parent.limit.Usage(); occupied != 1 {
		t.Fatal("wrong parent lease retained", occupied)
	}
	if _, e = parent.limit.TryAcquire(false); !errors.Is(e, forklimit.ErrCleanup) {
		t.Fatal("parent debt forgiven", e)
	}
	unrelated, e := independent.limit.TryAcquire(false)
	if e != nil {
		t.Fatal("independent parent poisoned", e)
	}
	unrelated.Cancel()
	parent.limit.Close()
	_ = d.retryCleanup(context.Background())
	if _, e = parent.limit.TryAcquire(false); !errors.Is(e, forklimit.ErrClosed) {
		t.Fatal("closed parent recovered", e)
	}
}
