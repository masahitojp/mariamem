package mariamem

import (
	"context"
	"errors"
	"sync"

	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// SnapshotOptions configures cold snapshot creation.
type SnapshotOptions struct {
	Rollback bool
}

// Snapshot owns a fixed, verified baseline. Child writes never update it. Do not copy.
type Snapshot struct {
	mu       sync.RWMutex
	backing  *stored.Owned
	opts     Options
	closed   bool
	closeErr error
}

// Snapshot consumes the DB on success, or on failure after host acceptance.
// It forwards ctx unchanged: no default snapshot timeout is imposed. The existing
// copy/hash phase is not context-interruptible. Precondition rejection leaves DB alive.
func (db *Database) Snapshot(ctx context.Context, opts SnapshotOptions) (*Snapshot, error) {
	ctx, finishTiming := timing.Begin(ctx, "public_snapshot")
	defer finishTiming()
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
		db.closeErr = hostError(db.removeTemporary(), "close", true)
		e = errors.Join(e, db.closeErr)
	}
	if e == nil && backing == nil {
		e = errors.New("missing verified snapshot backing")
	}
	if e != nil {
		return nil, hostError(errors.Join(e, backing.Close()), "snapshot_failed", consumed)
	}
	return &Snapshot{opts: db.opts, backing: backing}, nil
}

// Fork inherits the original DB options. Multiple startups can run concurrently.
// The read lock pins owned files through startup; a waiting Close blocks new
// readers and removes those files only after all admitted startups finish.
func (s *Snapshot) Fork(ctx context.Context) (*Database, error) {
	ctx, finishTiming := timing.Begin(ctx, "fork")
	defer finishTiming()
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.closed || s.backing == nil {
		return nil, hostError(ErrClosed, "closed", true)
	}
	timing.Mark(ctx, "snapshot_handle_ready")
	db, err := start(ctx, s.opts, s.backing)
	timing.Mark(ctx, "startup_returned")
	return db, err
}

// Close releases owned backing after admitted startups.
// Successfully started children remain usable after Close.
func (s *Snapshot) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return s.closeErr
	}
	s.closed = true
	s.closeErr = s.backing.Close()
	return s.closeErr
}
