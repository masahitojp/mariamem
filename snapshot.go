package mariamem

import (
	"context"
	"errors"
	"sync"

	"github.com/masahitojp/mariamem/internal/forklimit"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// SnapshotOptions configures cold snapshot creation.
type SnapshotOptions struct {
	Rollback bool
	// MaxForks limits reserved, starting, live and cleaning-up children.
	// Zero resolves a finite memory-based default once at capture. Positive
	// values through 2147483647 override it; there is no unlimited sentinel.
	MaxForks int
}

// Snapshot owns a fixed baseline with private backing. Child writes never update it.
// Do not copy.
type Snapshot struct {
	mu        sync.RWMutex
	backing   *stored.Owned
	opts      Options
	closed    bool
	closeErr  error
	limitOnce sync.Once
	limit     *forklimit.Pool
}

// Snapshot consumes the DB on success, or on failure after host acceptance.
// It forwards ctx unchanged: no default snapshot timeout is imposed. The existing
// sealing phase is not context-interruptible; borrowed mappings also require
// copying and validation. Precondition rejection leaves DB alive.
func (db *Database) Snapshot(ctx context.Context, opts SnapshotOptions) (*Snapshot, error) {
	ctx, finishTiming := timing.Begin(ctx, "public_snapshot")
	defer finishTiming()
	capacity, err := forklimit.Resolve(opts.MaxForks)
	if err != nil {
		return nil, &HostError{Code: "invalid_options", Stage: "snapshot_options", Err: err}
	}
	limit, err := forklimit.New(capacity)
	if err != nil {
		return nil, err
	}
	db.mu.Lock()
	defer db.mu.Unlock()
	if err := db.invalidLocked(); err != nil {
		return nil, err
	}
	if db.closed || db.server == nil {
		return nil, hostError(ErrClosed, "closed", true)
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	backing, consumed, e := db.server.SnapshotHeap(ctx, opts.Rollback)
	if consumed {
		db.closed = true
		db.closeErr = hostError(db.removeTemporaryAfter(e), "close", true)
		e = errors.Join(e, db.closeErr)
	}
	if e == nil && backing == nil {
		e = errors.New("missing verified snapshot backing")
	}
	if e != nil {
		cleanup := backing.Close()
		e = errors.Join(e, cleanup)
		if cleanup != nil && db.lease != nil {
			db.captureDebt = errors.Join(db.captureDebt, cleanup)
			db.lease.Settle(cleanup)
		}
		if consumed {
			db.settleFork(e, cleanup == nil && db.disposalComplete())
		}
		return nil, hostError(e, "snapshot_failed", consumed)
	}
	if consumed {
		db.settleFork(db.closeErr, db.disposalComplete())
	}
	return &Snapshot{opts: db.opts, backing: backing, limit: limit}, nil
}

// MaxForks returns this baseline's immutable resolved limit. The automatic
// default is a memory heuristic, not a CPU/latency optimum or OOM guarantee.
func (s *Snapshot) MaxForks() int { return s.forkLimit().MaxForks() }

func (s *Snapshot) forkLimit() *forklimit.Pool {
	s.limitOnce.Do(func() {
		// Private controlled test owners can construct a baseline directly.
		if s.limit == nil {
			n, _ := forklimit.Resolve(0)
			s.limit, _ = forklimit.New(n)
		}
	})
	return s.limit
}

// Fork inherits the original DB options. Multiple startups can run concurrently.
// The read lock pins owned files through startup; a waiting Close blocks new
// readers and removes those files only after all admitted startups finish.
func (s *Snapshot) Fork(ctx context.Context) (*Database, error) {
	ctx, finishTiming := timing.Begin(ctx, "fork")
	defer finishTiming()
	lease, err := s.forkLimit().Acquire(ctx)
	if err != nil {
		return nil, forkAdmissionError(s.forkLimit().Describe(err))
	}
	return s.forkReserved(ctx, lease)
}

func (s *Snapshot) forkReserved(ctx context.Context, lease *forklimit.Lease) (*Database, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.closed || s.backing == nil {
		lease.Cancel()
		return nil, hostError(ErrClosed, "closed", true)
	}
	if err := lease.Activate(); err != nil {
		lease.Cancel()
		return nil, forkAdmissionError(s.forkLimit().Describe(err))
	}
	timing.Mark(ctx, "snapshot_handle_ready")
	db, err := startLeased(ctx, s.opts, s.backing, lease)
	timing.Mark(ctx, "startup_returned")
	return db, err
}

// Close releases owned backing after admitted startups.
// Successfully started children remain usable after Close.
func (s *Snapshot) Close() error {
	s.forkLimit().Close()
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return s.closeErr
	}
	s.closed = true
	s.closeErr = s.backing.Close()
	return s.closeErr
}

func forkAdmissionError(err error) error {
	code, stage, closed := "pool_timeout", "fork_wait", false
	switch {
	case errors.Is(err, forklimit.ErrCleanup):
		code, stage = "unusable", "fork_admission"
	case errors.Is(err, forklimit.ErrClosed):
		code, closed = "closed", true
	case errors.Is(err, forklimit.ErrFull):
		code = "busy"
	case errors.Is(err, forklimit.ErrLease):
		code, stage = "invalid_options", "fork_options"
	}
	return &HostError{Code: code, Stage: stage, Closed: closed, Err: err}
}
