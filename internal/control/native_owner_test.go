package control

import (
	"context"
	"errors"
	"testing"
	"time"

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
