package mariamem

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"

	"github.com/masahitojp/mariamem/internal/artifacts"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// SnapshotOptions configures cold snapshot creation.
type SnapshotOptions struct {
	Destination string // Empty creates a temporary snapshot owned by the handle.
	Rollback    bool
}

// Snapshot owns a fixed, verified baseline. Child writes never update it. Do not copy.
type Snapshot struct {
	mu              sync.RWMutex
	path, temporary string
	backing         *stored.Owned
	opts            Options
	closed          bool
	closeErr        error
}

// LoadSnapshot validates and imports a persisted baseline without starting MariaDB.
// The returned Snapshot owns an independent copy of the verified backing; changing
// or deleting path after success does not affect Fork. Close never deletes path.
// opts configures subsequent Forks. Copying/hashing is not interruptible: ctx is
// checked before import and after it, releasing acquired resources on cancellation.
func LoadSnapshot(ctx context.Context, path string, opts Options) (*Snapshot, error) {
	opts, err := opts.defaults()
	if err != nil {
		return nil, err
	}
	if err = ctx.Err(); err != nil {
		return nil, err
	}
	if err = rejectLegacyRuntime(opts.NativeDir); err != nil {
		return nil, hostError(err, "artifacts", false)
	}
	if err = artifacts.ValidatePlatform(ctx); err != nil {
		return nil, hostError(err, "platform", false)
	}
	backing, err := stored.Import(path, runtimekind.GuestSHA256)
	if err != nil {
		return nil, hostError(err, "snapshot_failed", false)
	}
	if err = ctx.Err(); err != nil {
		return nil, errors.Join(err, backing.Close())
	}
	return &Snapshot{backing: backing, opts: opts}, nil
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
	timing.Mark(ctx, "destination_ready")
	consumed, err := db.server.Snapshot(ctx, saved.path, opts.Rollback)
	timing.Mark(ctx, "host_snapshot_returned")
	if consumed {
		db.closed = true
		db.closeErr = hostError(db.removeTemporary(), "close", true)
		err = errors.Join(err, db.closeErr)
	}
	timing.Mark(ctx, "source_cleanup_done")
	if err == nil {
		if saved.temporary != "" {
			saved.backing, err = stored.AdoptCreated(saved.path, db.build)
		} else {
			saved.backing, err = stored.Import(saved.path, db.build)
		}
	}
	timing.Mark(ctx, "owned_backing_acquired")
	if err != nil {
		return nil, hostError(errors.Join(err, saved.Close()), "snapshot_failed", consumed)
	}
	return saved, nil
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

// Close releases owned backing after admitted startups. It retains explicit destinations.
// Successfully started children remain usable after Close.
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
