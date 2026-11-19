package host

import (
	"context"
	"errors"
	"fmt"

	"github.com/masahitojp/mariamem/internal/guest"

	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

func (s *Server) SnapshotHeap(ctx context.Context, rollback bool) (owned *snapshot.Owned, consumed bool, err error) {
	ctx, finish := timing.Begin(ctx, "snapshot_capture")
	defer finish()
	s.mu.Lock()
	if !s.SnapshotCapable() {
		s.mu.Unlock()
		return nil, false, &Rejected{"unsupported", "guest does not support snapshots"}
	}
	if s.closing {
		s.mu.Unlock()
		return nil, false, &Rejected{"closed", "database is closing"}
	}
	if e := s.snapshotPrecondition(rollback); e != nil {
		s.mu.Unlock()
		return nil, false, e
	}
	if e := ctx.Err(); e != nil {
		s.mu.Unlock()
		return nil, false, e
	}
	s.Guest.RequestCapture()
	s.stopAccepting()
	s.mu.Unlock()
	defer func() { err = s.disposeAfter(err) }()
	if e := s.finish(ctx, shutdownCapture); e != nil {
		s.Guest.DiscardCapture()
		return nil, true, e
	}
	image, takeErr := s.Guest.TakeRoot(s.build)
	if takeErr != nil {
		return nil, true, takeErr
	}
	if image == nil {
		return nil, true, errors.New("missing snapshot capture")
	}

	owned, e := snapshot.OwnRoot(image, s.build)
	for key, v := range image.Counts() {
		timing.Work(ctx, "root/"+key+"/read", v.Read, 0)
		timing.Work(ctx, "root/"+key+"/copy", v.Copy, 0)
		timing.Work(ctx, "root/"+key+"/hash", v.Hash, 0)
		timing.Work(ctx, "root/"+key+"/zero", v.Zero, v.Metadata)
	}
	return owned, true, e
}

// errLockWaitTimeout is MariaDB ER_LOCK_WAIT_TIMEOUT. With lock_wait_timeout=0,
// FLUSH TABLES WITH READ LOCK returns it at once when an idle session holds
// LOCK TABLES ... WRITE (its backup DML lock conflicts with the global read lock).
const errLockWaitTimeout = 1205

// SnapshotKeep captures committed state without stopping the instance. Existing
// idle sessions stay attached to the same guest sessions; the source keeps
// copy-on-write files and continues accepting SQL afterwards.
//
// It waits for in-flight handshakes, commands and session cleanup to finish
// (bounded by ctx), then rejects a session with an open transaction. Once
// accepted, SQL admission is held for the whole private global read lock,
// checkpoint and cut; an idle LOCK TABLES ... WRITE holder is rejected as busy;
// that phase is not context-interruptible, because cancelling a guest call
// aborts the instance. If neither lock release nor session closure can be
// confirmed after acquiring the lock, abort the guest.
func (s *Server) SnapshotKeep(ctx context.Context) (owned *snapshot.Owned, err error) {
	ctx, finish := timing.Begin(ctx, "snapshot_keep")
	defer finish()
	s.mu.Lock()
	for {
		if e := s.keepPreconditionLocked(); e != nil {
			s.mu.Unlock()
			return nil, e
		}
		if !s.anyBusyLocked() {
			break
		}
		if s.activityChanged == nil {
			s.activityChanged = make(chan struct{})
		}
		changed := s.activityChanged
		s.mu.Unlock()
		select {
		case <-changed:
		case <-s.Guest.FailureDone():
		case <-s.Guest.Done():
		case <-ctx.Done():
			return nil, ctx.Err()
		}
		s.mu.Lock()
	}
	if e := ctx.Err(); e != nil {
		s.mu.Unlock()
		return nil, e
	}
	slot, ok := s.allocateSlotLocked()
	if !ok {
		s.mu.Unlock()
		return nil, &Rejected{"capacity", "snapshot requires one free session slot"}
	}
	defer s.mu.Unlock()
	timing.Mark(ctx, "sessions_quiesced")
	guestCtx := context.WithoutCancel(ctx)
	call := func(op byte, sql string) (guest.Result, error) {
		r, e := s.Guest.Call(guestCtx, op, slot, []byte(sql))
		if e != nil {
			return r, e
		}
		if !r.OK || r.Errno != 0 || r.Error != "" {
			return r, fmt.Errorf("snapshot keep operation %d %q: errno %d: %s", op, sql, r.Errno, r.Error)
		}
		return r, nil
	}
	opened, e := s.Guest.Call(guestCtx, 1, slot, nil)
	if e != nil {
		// No reply: the guest session state is unknown, so keep the slot
		// reserved. A transport failure also fails the instance.
		return nil, e
	}
	if !opened.OK {
		// The guest answered that it did not open a session (for example, the
		// default database is missing). As in mysqlwire.Serve, nothing needs
		// closing, so the slot is reusable and a repaired source can retry.
		s.slots[slot] = false
		return nil, fmt.Errorf("snapshot keep session open: errno %d: %s", opened.Errno, opened.Error)
	}
	var unlockErr error
	defer func() {
		r, e := s.Guest.Call(guestCtx, 3, slot, nil)
		if e == nil && !r.Closed {
			e = errors.New("snapshot keep session did not close")
		}
		if e != nil {
			err = errors.Join(err, e)
			if unlockErr != nil {
				s.Guest.Abort(err)
			}
			return // keep the slot reserved: its guest session state is unknown
		}
		s.slots[slot] = false
	}()
	if opened.Errno != 0 || opened.Error != "" {
		// Opened with an error report: close it through the deferred path.
		return nil, fmt.Errorf("snapshot keep session open: errno %d: %s", opened.Errno, opened.Error)
	}
	if _, err = call(2, "SET SESSION lock_wait_timeout=0"); err != nil {
		return nil, err
	}
	// A prepared XA transaction survives its client's disconnect and has no
	// session status flag. The engine would carry it into every child, where a
	// later XA COMMIT applies parent work that the baseline must not contain.
	// Admission is held, so no session can prepare one before the cut.
	if r, e := call(2, "XA RECOVER"); e != nil {
		return nil, e
	} else if len(r.Rows)+len(r.RawRows) != 0 {
		return nil, &Rejected{"transaction_active", "a prepared XA transaction exists; run XA COMMIT or XA ROLLBACK first"}
	}
	// The global read lock flushes every table and is held until the cut is
	// complete. Plain FLUSH TABLES neither waits for nor reports LOCK TABLES
	// WRITE holders, whose unflushed MyISAM/Aria state would be captured.
	if r, e := call(2, "FLUSH TABLES WITH READ LOCK"); e != nil {
		if r.Errno == errLockWaitTimeout {
			return nil, &Rejected{"busy", "a session holds LOCK TABLES ... WRITE; run UNLOCK TABLES first"}
		}
		return nil, e
	}
	// Runs before the session close above. Closing the session also releases
	// the lock, so an UNLOCK failure is reported but still followed by close.
	defer func() {
		_, unlockErr = call(2, "UNLOCK TABLES")
		if unlockErr != nil {
			err = errors.Join(err, unlockErr)
		}
	}()
	timing.Mark(ctx, "tables_flushed")
	// Write back all dirty pages and checkpoint, so children start without
	// redo recovery. This is synchronous in MariaDB 12.3 release builds.
	if _, err = call(2, "SET GLOBAL innodb_log_checkpoint_now=ON"); err != nil {
		return nil, err
	}
	timing.Mark(ctx, "engine_checkpointed")
	root, err := s.Guest.KeepRoot()
	if err != nil {
		return nil, err
	}
	timing.Mark(ctx, "files_cut")
	return snapshot.OwnRoot(root, s.build)
}

// keepPreconditionLocked requires s.mu.
func (s *Server) keepPreconditionLocked() error {
	if !s.SnapshotCapable() {
		return &Rejected{"unsupported", "guest does not support snapshots"}
	}
	if s.closing {
		return &Rejected{"closed", "database is closing"}
	}
	if cause := s.Guest.Err(); cause != nil {
		return errors.Join(&Rejected{"unusable", "database instance terminated"}, cause)
	}
	for _, state := range s.clients {
		if !state.busy && state.status&1 != 0 {
			return &Rejected{"transaction_active", "commit or roll back open transactions before a snapshot that keeps the database"}
		}
	}
	return nil
}

func (s *Server) anyBusyLocked() bool {
	for _, state := range s.clients {
		if state.busy {
			return true
		}
	}
	return false
}
