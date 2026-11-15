package mariamem

import (
	"context"
	"github.com/masahitojp/mariamem/internal/disposal"
	"sync"
)

// An operation result ends an attempt; disposal success is a separate fact.
// The stopped boundary is supplied by the host backend.
type closeOperation struct {
	stopped chan struct{}
	done    chan struct{}
	once    sync.Once
	stopErr error // published by closing stopped
	err     error // published by closing done
	confirm func() bool
}

func newCloseOperation() *closeOperation {
	return &closeOperation{stopped: make(chan struct{}), done: make(chan struct{})}
}
func (o *closeOperation) notifyStopped(err error) {
	o.once.Do(func() { o.stopErr = err; close(o.stopped) })
}
func (o *closeOperation) Wait(ctx context.Context) error {
	if err := disposal.Wait(ctx, o.done); err != nil {
		return err
	}
	return o.err
}

// A failed attempt may be reclaimed later without rewriting its saved error.
func (o *closeOperation) Disposed() bool {
	select {
	case <-o.done:
	default:
		return false
	}
	return !cleanupPending(o.err) && o.confirm != nil && o.confirm()
}

// CloseHandle observes an owned asynchronous Close. It is safe for concurrent
// waiters. A failed initial cleanup result remains failed after later recovery.
// Obtain handles through Database.CloseAsync; the zero value is invalid.
type CloseHandle struct{ operation *closeOperation }

// CloseAsync rejects new work immediately and waits until guest execution,
// transport readers and host sessions have stopped. Resource cleanup continues
// in the background. Close joins the same operation and still waits for cleanup.
// A canceled context before initiation returns nil; cancellation after initiation
// returns a non-nil handle and an error. Always retain a non-nil handle and Wait
// for the cleanup attempt, even when CloseAsync returns an error.
// Fork capacity remains occupied until disposal is confirmed.
func (db *Database) CloseAsync(ctx context.Context) (*CloseHandle, error) {
	op, err := db.stopForCleanup(ctx)
	if op == nil {
		return nil, err
	}
	return &CloseHandle{operation: op}, err
}

// Wait waits for the initial cleanup attempt and returns its stable result.
// Context cancellation cancels this wait only. A nil result confirms disposal;
// a cleanup error may retain resources and the Fork slot. Close returns the same
// operation result. Later recovery does not rewrite that result.
func (h *CloseHandle) Wait(ctx context.Context) error { return h.operation.Wait(ctx) }

// Disposed reports confirmed reclamation, independently of the stored error.
// It may become true after a failed cleanup is recovered by an existing owner.
func (h *CloseHandle) Disposed() bool { return h.operation.Disposed() }
