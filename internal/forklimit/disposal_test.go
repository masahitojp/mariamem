package forklimit

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
)

func TestLateStartupDisposalRetainsLeaseAndNeedsExplicitRecovery(t *testing.T) {
	p := pool(t, 1)
	l := active(t, p)
	joined := make(chan struct{})
	var once sync.Once
	t.Cleanup(func() { once.Do(func() { close(joined) }) })
	owner := disposal.New(func(ctx context.Context) error { return disposal.Wait(ctx, joined) })
	cause := errors.New("failed startup, still joining")
	err := disposal.Retain(cause, context.DeadlineExceeded, owner)
	l.TrackCleanup(err)
	l.TrackCleanup(err)
	if _, e := p.TryAcquire(true); !errors.Is(e, cause) {
		t.Fatal("released before join", e)
	}
	// Observe the state change with the pool's own notification, not sleeps.
	once.Do(func() { close(joined) })
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	for {
		p.mu.Lock()
		remaining, changed := len(p.leases), p.changed
		p.mu.Unlock()
		if remaining == 0 {
			break
		}
		select {
		case <-changed:
		case <-ctx.Done():
			t.Fatal("late disposal did not settle lease")
		}
	}
	if _, e := p.TryAcquire(false); !errors.Is(e, ErrCleanup) {
		t.Fatal("automatic admission recovery", e)
	}
	next, e := p.TryAcquire(true)
	if e != nil {
		t.Fatal(e)
	}
	next.Settle(nil)
	if !errors.Is(err, cause) {
		t.Fatal("original failure lost")
	}
}

func TestUnknownCleanupCannotReleaseLeaseByMessage(t *testing.T) {
	p := pool(t, 1)
	l := active(t, p)
	l.TrackCleanup(errors.New("guest completed successfully, cleanup maybe done"))
	if _, err := p.TryAcquire(true); !errors.Is(err, ErrCleanup) {
		t.Fatal(err)
	}
	p.Close()
	if len(p.leases) != 1 {
		t.Fatal("Close discarded unknown owner")
	}
	l.Settle(nil) // Test owner's explicit disposal confirmation.
}
