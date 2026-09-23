package mariamem

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"

	stored "mariamem/internal/snapshot"
)

type SnapshotOptions struct {
	Destination string // Empty creates a temporary snapshot owned by the handle.
	Rollback    bool
}

// Snapshot owns only snapshots created with an empty Destination. Do not copy.
type Snapshot struct {
	mu              sync.Mutex
	path, temporary string
	opts            Options
	closed          bool
	closeErr        error
}

// Snapshot consumes the DB on success, or on failure after host acceptance.
// It forwards ctx unchanged: no default snapshot timeout is imposed. The existing
// copy/hash phase is not context-interruptible. Precondition rejection leaves DB alive.
func (db *Database) Snapshot(ctx context.Context, opts SnapshotOptions) (*Snapshot, error) {
	db.mu.Lock()
	defer db.mu.Unlock()
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
		_, err = stored.Validate(saved.path, db.build)
	}
	if err != nil {
		return nil, hostError(errors.Join(err, saved.Close()), "snapshot_failed", consumed)
	}
	return saved, nil
}
func (s *Snapshot) Path() string { return s.path }

// Fork inherits the original DB options. Close is serialized with startup so an
// owned snapshot cannot be removed while its initial data is being restored.
func (s *Snapshot) Fork(ctx context.Context) (*Database, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed || s.path == "" {
		return nil, hostError(ErrClosed, "closed", true)
	}
	return start(ctx, s.opts, s.path)
}

// Close retains explicit destinations and removes only this handle's temp root.
func (s *Snapshot) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return s.closeErr
	}
	s.closed = true
	if s.temporary != "" {
		s.closeErr = os.RemoveAll(s.temporary)
	}
	return s.closeErr
}
