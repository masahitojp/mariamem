package mariamem

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"

	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// SnapshotOptions configures cold snapshot creation.
type SnapshotOptions struct {
	Destination string // Empty creates a temporary snapshot owned by the handle.
	Rollback    bool
}

// Snapshot owns an unlinked, verified backing for every destination. Do not copy.
type Snapshot struct {
	mu              sync.RWMutex
	path, temporary string
	opts            Options
	closed          bool
	closeErr        error
	backing         *stored.Owned
}

// Snapshot consumes the DB on success, or on failure after host acceptance.
// It forwards ctx unchanged: no default snapshot timeout is imposed. The existing
// copy/hash phase is not context-interruptible. Precondition rejection leaves DB alive.
func (db *Database) Snapshot(ctx context.Context, opts SnapshotOptions) (*Snapshot, error) {
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
	saved := &Snapshot{opts: db.opts}
	var err error
	if opts.Destination == "" {
		saved.temporary, err = os.MkdirTemp("", "mariamem-snapshot-")
		if err != nil {
			return nil, err
		}
		saved.path = filepath.Join(saved.temporary, "snapshot")
	} else {
		saved.path, err = filepath.Abs(opts.Destination)
		if err != nil {
			return nil, err
		}
	}
	consumed, err := db.server.Snapshot(ctx, saved.path, opts.Rollback)
	if consumed {
		db.closed = true
		db.closeErr = hostError(db.removeTemporary(), "close", true)
		err = errors.Join(err, db.closeErr)
	}
	if err == nil {
		if saved.temporary != "" {
			saved.backing, err = stored.AdoptCreated(saved.path, db.build)
		} else {
			// Keep path-write API policy separate from this spike. The exported
			// artifact is external; Fork uses an independently imported backing.
			saved.backing, err = stored.Import(saved.path, db.build)
		}
	}
	if err != nil {
		return nil, hostError(errors.Join(err, saved.Close()), "snapshot_failed", consumed)
	}
	return saved, nil
}

// Path returns the staging/export path for compatibility. Temporary staging is
// removed after acquisition. Fork never reads this path.
func (s *Snapshot) Path() string { return s.path }

// Fork inherits the original DB options. Multiple startups can run concurrently.
// The read lock pins owned files through startup; a waiting Close blocks new
// readers and removes those files only after all admitted startups finish.
func (s *Snapshot) Fork(ctx context.Context) (*Database, error) {
	ctx, finishTiming := timing.Begin(ctx, "fork")
	defer finishTiming()
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.closed || s.path == "" {
		return nil, hostError(ErrClosed, "closed", true)
	}
	timing.Mark(ctx, "snapshot_handle_ready")
	db, err := start(ctx, s.opts, s.backing)
	timing.Mark(ctx, "startup_returned")
	return db, err
}

// Close retains explicit destinations and removes only this handle's temp root.
func (s *Snapshot) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return s.closeErr
	}
	s.closed = true
	s.closeErr = s.backing.Close()
	if s.temporary != "" {
		s.closeErr = errors.Join(s.closeErr, os.RemoveAll(s.temporary))
	}
	return s.closeErr
}
