package forklimit

import (
	"context"
	"errors"
	"strings"
	"sync"
	"testing"
	"time"
)

func pool(t *testing.T, n int) *Pool {
	t.Helper()
	p, err := New(n)
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func active(t *testing.T, p *Pool) *Lease {
	t.Helper()
	l, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Activate(); err != nil {
		t.Fatal(err)
	}
	return l
}

func TestConcurrentBoundAndProgress(t *testing.T) {
	for _, cap := range []int{1, 2} {
		t.Run(string(rune('0'+cap)), func(t *testing.T) {
			p := pool(t, cap)
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			entered := make(chan *Lease, 4)
			release := make(chan struct{})
			var wg sync.WaitGroup
			for range 4 {
				wg.Add(1)
				go func() {
					defer wg.Done()
					l, err := p.Acquire(ctx)
					if err != nil {
						t.Error(err)
						return
					}
					if err := l.Activate(); err != nil {
						t.Error(err)
						return
					}
					entered <- l
					select {
					case <-release:
					case <-ctx.Done():
						t.Error(ctx.Err())
					}
					l.Settle(nil)
				}()
			}
			for i := 0; i < 4; i += cap {
				for range cap {
					select {
					case <-entered:
					case <-ctx.Done():
						t.Fatal(ctx.Err())
					}
				}
				p.mu.Lock()
				count := len(p.leases)
				p.mu.Unlock()
				if count != cap {
					t.Fatalf("occupied=%d cap=%d", count, cap)
				}
				if _, err := p.TryAcquire(false); !errors.Is(err, ErrFull) {
					t.Fatalf("over-admission: %v", err)
				}
				for range cap {
					release <- struct{}{}
				}
			}
			wg.Wait()
			p.mu.Lock()
			defer p.mu.Unlock()
			if len(p.leases) != 0 {
				t.Fatal("leaked leases")
			}
		})
	}
}

func TestCloseWakesWaiterWhileChildRemains(t *testing.T) {
	p := pool(t, 1)
	child := active(t, p)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	done := make(chan error, 1)
	observed := &waitingContext{Context: ctx, waiting: make(chan struct{})}
	go func() { _, err := p.Acquire(observed); done <- err }()
	select {
	case <-observed.waiting:
	case <-ctx.Done():
		t.Fatal("waiter never reached capacity wait")
	}
	p.Close()
	if err := <-done; !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	// Successful child ownership survives. Close does not falsely settle it.
	if len(p.leases) != 1 {
		t.Fatal("Close released an active child")
	}
	child.Settle(nil)
	child.Settle(nil)
	if len(p.leases) != 0 {
		t.Fatal("child not settled")
	}
	if _, err := p.TryAcquire(true); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
}

// Done is evaluated in Acquire's wait select, after the full result and after
// capturing the wake channel. This barrier avoids a sleep or production hook.
type waitingContext struct {
	context.Context
	once    sync.Once
	waiting chan struct{}
}

func (c *waitingContext) Done() <-chan struct{} {
	c.once.Do(func() { close(c.waiting) })
	return c.Context.Done()
}

func TestDebtWakesBlockedWaiterAndRetainsCause(t *testing.T) {
	p := pool(t, 1)
	l := active(t, p)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	observed := &waitingContext{Context: ctx, waiting: make(chan struct{})}
	done := make(chan error, 1)
	go func() { _, err := p.Acquire(observed); done <- err }()
	select {
	case <-observed.waiting:
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	cause := errors.New("disposal unconfirmed")
	l.Settle(cause)
	if err := <-done; !errors.Is(err, ErrCleanup) || !errors.Is(err, cause) {
		t.Fatal(err)
	}
	l.Settle(nil)
}

func TestFailedRetryRetainsCapacity(t *testing.T) {
	p := pool(t, 2)
	a, b := active(t, p), active(t, p)
	a.Settle(errors.New("cleanup failure"))
	// Occupancy is retained during retries, including a failed repeat.
	a.Settle(errors.New("retry failed"))
	if _, err := p.TryAcquire(true); !errors.Is(err, ErrCleanup) {
		t.Fatal(err)
	}
	a.Settle(nil)
	newLease, err := p.TryAcquire(true)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := p.TryAcquire(true); !errors.Is(err, ErrFull) {
		t.Fatal(err)
	}
	newLease.Settle(nil)
	b.Settle(nil)
}

func TestCleanupCauseIsNotMistakenForCapacityWait(t *testing.T) {
	p := pool(t, 1)
	l := active(t, p)
	l.Settle(ErrFull)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if _, err := p.Acquire(ctx); !errors.Is(err, ErrCleanup) || !errors.Is(err, ErrFull) {
		t.Fatalf("cleanup must fail admission, not enter capacity wait: %v", err)
	}
	l.Settle(nil)
}

func TestUnusedReservationRevokedAndDuplicateActivationRejected(t *testing.T) {
	p := pool(t, 2)
	child := active(t, p)
	if err := child.Activate(); !errors.Is(err, ErrLease) {
		t.Fatal(err)
	}
	unused, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	p.Close()
	if len(p.leases) != 1 {
		t.Fatal("unused reservation was not revoked")
	}
	if err := unused.Activate(); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	unused.Settle(nil)
	if len(p.leases) != 1 {
		t.Fatal("late settlement released another child")
	}
	child.Settle(nil)
}

func TestCleanupDebtRequiresExplicitRecoveryOfAllOwners(t *testing.T) {
	p := pool(t, 2)
	old, candidate := active(t, p), active(t, p)
	a, b := errors.New("old cleanup failed"), errors.New("candidate cleanup failed")
	old.Settle(a)
	candidate.Settle(b)
	if _, err := p.TryAcquire(true); !errors.Is(err, a) || !errors.Is(err, b) {
		t.Fatal(err)
	}
	old.Settle(nil)
	if _, err := p.TryAcquire(true); !errors.Is(err, b) {
		t.Fatal(err)
	}
	candidate.Settle(nil)
	if _, err := p.TryAcquire(false); !errors.Is(err, ErrCleanup) || !errors.Is(err, a) {
		t.Fatal("automatic recovery", err)
	}
	replacement, err := p.TryAcquire(true)
	if err != nil {
		t.Fatal(err)
	}
	if err := replacement.Activate(); err != nil {
		t.Fatal(err)
	}
	old.Settle(a) // stale/duplicate ack cannot poison a new lease
	candidate.Settle(nil)
	other := active(t, p)
	if _, err := p.TryAcquire(false); !errors.Is(err, ErrFull) {
		t.Fatal(err)
	}
	replacement.Settle(nil)
	other.Settle(nil)
}

func TestRecoveryAndNewDebtRaceNeverForgivesOtherOwner(t *testing.T) {
	for range 100 {
		p := pool(t, 2)
		old, other := active(t, p), active(t, p)
		old.Settle(errors.New("first debt"))
		old.Settle(nil)
		var recovered *Lease
		var wg sync.WaitGroup
		wg.Add(2)
		go func() { defer wg.Done(); recovered, _ = p.TryAcquire(true) }()
		go func() { defer wg.Done(); other.Settle(errors.New("new debt")) }()
		wg.Wait()
		if recovered != nil {
			if err := recovered.Activate(); !errors.Is(err, ErrCleanup) {
				t.Fatal(err)
			}
			recovered.Settle(nil)
		}
		if _, err := p.TryAcquire(true); !errors.Is(err, ErrCleanup) {
			t.Fatal(err)
		}
		other.Settle(nil)
	}
}

func TestCloseWinsRecoveryRace(t *testing.T) {
	for range 100 {
		p := pool(t, 1)
		l := active(t, p)
		l.Settle(errors.New("cleanup"))
		l.Settle(nil)
		var recovered *Lease
		var wg sync.WaitGroup
		wg.Add(2)
		go func() { defer wg.Done(); recovered, _ = p.TryAcquire(true) }()
		go func() { defer wg.Done(); p.Close() }()
		wg.Wait()
		if recovered != nil {
			if err := recovered.Activate(); !errors.Is(err, ErrClosed) {
				t.Fatal(err)
			}
			recovered.Settle(nil)
		}
		if len(p.leases) != 0 {
			t.Fatal("reservation survived Close")
		}
	}
}

func TestCancellationAndIndependentPools(t *testing.T) {
	p, other := pool(t, 1), pool(t, 1)
	l := active(t, p)
	second := active(t, other)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { _, err := p.Acquire(ctx); done <- err }()
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatal(err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("cancel did not wake waiter")
	}
	l.Settle(nil)
	second.Settle(nil)
	if _, err := p.Acquire(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
}

func TestMaximumDoesNotAllocateCapacitySizedStorage(t *testing.T) {
	p := pool(t, int(MaxForks))
	if p.MaxForks() != int(MaxForks) || len(p.leases) != 0 {
		t.Fatal("invalid maximum")
	}
	l := active(t, p)
	l.Settle(nil)
	for _, n := range []int{-1, 0, int(MaxForks) + 1} {
		if _, err := New(n); err == nil {
			t.Fatal("accepted", n)
		}
	}
}

func TestUsageIncludesReservationsAndUnconfirmedCleanupWithoutReopening(t *testing.T) {
	p := pool(t, 2)
	first, _ := p.TryAcquire(false)
	second, _ := p.TryAcquire(false)
	if cap, occupied := p.Usage(); cap != 2 || occupied != 2 {
		t.Fatal(cap, occupied)
	}
	_ = first.Activate()
	cause := errors.New("cleanup not confirmed")
	first.Settle(cause)
	second.Cancel()
	if cap, occupied := p.Usage(); cap != 2 || occupied != 1 {
		t.Fatal(cap, occupied)
	}
	_, debt := p.TryAcquire(false)
	err := p.Describe(debt)
	if !errors.Is(err, cause) || !errors.Is(err, ErrCleanup) || !strings.Contains(err.Error(), "max_forks=2, occupied_slots=1") {
		t.Fatal(err)
	}
	if strings.Contains(err.Error(), "increase max_forks") {
		t.Fatal("capacity tuning cannot resolve cleanup debt", err)
	}
	first.Settle(nil)
	if _, occupied := p.Usage(); occupied != 0 {
		t.Fatal(occupied)
	}
	if _, err := p.TryAcquire(false); !errors.Is(err, ErrCleanup) {
		t.Fatal("diagnostic observation reopened admission", err)
	}
	for _, cause := range []error{ErrFull, context.DeadlineExceeded, context.Canceled} {
		err := p.Describe(cause)
		if !errors.Is(err, cause) || !strings.Contains(err.Error(), "max_forks=2, occupied_slots=0") || !strings.Contains(err.Error(), "close owned children or increase max_forks") {
			t.Fatal(err)
		}
	}
	if p.Describe(nil) != nil {
		t.Fatal("nil became a diagnostic error")
	}
}
