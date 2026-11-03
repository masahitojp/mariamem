// Package forklimit owns per-Snapshot admission, independently of its backing.
// A lease counts from reservation until confirmed child disposal. Callers must
// keep the lease when cleanup is uncertain; an error is not proof of disposal.
package forklimit

import (
	"context"
	"errors"
	"sync"
)

var (
	ErrClosed  = errors.New("snapshot is closed")
	ErrFull    = errors.New("snapshot Fork capacity is full")
	ErrCleanup = errors.New("snapshot admission stopped after uncertain cleanup")
	ErrLease   = errors.New("Fork reservation is no longer available")
)

// Pool has immutable capacity and no capacity-sized allocation. Do not copy.
type Pool struct {
	mu              sync.Mutex
	limit           int
	closed, blocked bool
	cause           error
	changed         chan struct{}
	leases          map[*Lease]struct{}
}

// Lease has a single lifecycle owner. Its methods are safe against Pool.Close
// and duplicate settlement. After Activate, only confirmed cleanup releases it.
type Lease struct {
	pool   *Pool
	active bool
	debt   error
}

func New(limit int) (*Pool, error) {
	if limit < 1 || int64(limit) > MaxForks {
		return nil, errors.New("max_forks must be between 1 and 2147483647")
	}
	return &Pool{limit: limit, changed: make(chan struct{}), leases: make(map[*Lease]struct{})}, nil
}

func (p *Pool) MaxForks() int { return p.limit }

func (p *Pool) signal() { close(p.changed); p.changed = make(chan struct{}) }

func (p *Pool) acquireLocked(recover bool) (*Lease, error) {
	if p.closed {
		return nil, ErrClosed
	}
	if p.blocked {
		var debt error
		for l := range p.leases {
			debt = errors.Join(debt, l.debt)
		}
		if !recover || debt != nil {
			return nil, errors.Join(ErrCleanup, p.cause, debt)
		}
	}
	if len(p.leases) >= p.limit {
		return nil, ErrFull
	}
	// Explicit recovery and reservation are a single transition. Full capacity
	// or unresolved debt cannot reopen admission as a side effect.
	p.blocked = false
	p.cause = nil
	l := &Lease{pool: p}
	p.leases[l] = struct{}{}
	return l, nil
}

// TryAcquire never waits. recover is only for an explicit Live Reset after
// retrying its owned cleanup, never ordinary Fork or background disposal.
func (p *Pool) TryAcquire(recover bool) (*Lease, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.acquireLocked(recover)
}

// Acquire waits without holding the Snapshot's backing lock. Close wakes all
// waiters even while successful children remain alive. Fairness is not promised.
func (p *Pool) Acquire(ctx context.Context) (*Lease, error) {
	for {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		p.mu.Lock()
		l, err := p.acquireLocked(false)
		changed := p.changed
		p.mu.Unlock()
		if l != nil && ctx.Err() != nil {
			l.Settle(nil)
			return nil, ctx.Err()
		}
		if !errors.Is(err, ErrFull) {
			return l, err
		}
		select {
		case <-changed:
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}
}

// Close revokes unused reservations, but active child leases remain owned.
// Backing disposal and already admitted startups are joined by the caller.
func (p *Pool) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return
	}
	p.closed = true
	for l := range p.leases {
		if !l.active {
			delete(p.leases, l)
		}
	}
	p.signal()
}

// Activate is called while holding backing protection, before any startup or
// export allocation. It consumes the reservation exactly once. On rejection,
// the caller still settles its unused lease (Close may already have revoked it).
func (l *Lease) Activate() error {
	p := l.pool
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return ErrClosed
	}
	if _, ok := p.leases[l]; !ok || l.active {
		return ErrLease
	}
	if p.blocked {
		return errors.Join(ErrCleanup, p.cause)
	}
	l.active = true
	return nil
}

// Settle(nil) confirms disposal (or cancels an unused reservation). A cleanup
// error retains the slot and stops admission. Later successful settlement clears
// this lease's debt, but only explicit TryAcquire(true) can reopen the pool.
// No settlement can revive a closed pool or decrement a different lease.
func (l *Lease) Settle(cleanup error) {
	p := l.pool
	p.mu.Lock()
	defer p.mu.Unlock()
	if _, ok := p.leases[l]; !ok {
		return
	}
	if cleanup == nil {
		delete(p.leases, l)
	} else {
		// Retain even if failure happened before Activate, e.g. transfer scratch.
		l.active = true
		if l.debt == nil {
			l.debt = cleanup
		}
		if !p.blocked {
			p.cause = cleanup
		}
		p.blocked = true
	}
	p.signal()
}
