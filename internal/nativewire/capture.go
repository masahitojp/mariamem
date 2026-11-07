package nativewire

import (
	"context"
	"errors"
	"fmt"

	"github.com/masahitojp/mariamem/internal/disposal"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
)

// Rejected is a definitive, non-consuming guest capture rejection. Public
// adapters map its Code to the existing busy/transaction errors.
type Rejected struct {
	Code    string
	Message string
}

func (e *Rejected) Error() string { return e.Message }

func (r *Backend) captureFailure(ctx context.Context, cause error) (*stored.Owned, bool, error) {
	r.mu.Lock()
	r.consumed = true
	r.checking = false
	r.owner.EndCaptureLocked()
	r.mu.Unlock()
	r.fail(cause)
	e := r.disposer.Retry(ctx)
	if e != nil {
		return nil, true, disposal.Retain(cause, e, r.disposer)
	}
	return nil, true, cause
}
func (r *Backend) endCheck() {
	r.mu.Lock()
	r.checking = false
	r.owner.EndCaptureLocked()
	r.mu.Unlock()
}

// SnapshotHeap always asks the guest's final atomic fence. Busy is merely an
// advisory STATE cache and never authorizes capture. After acceptance every
// error is consuming, even if physical join remains pending.
func (r *Backend) SnapshotHeap(ctx context.Context, rollback bool) (*stored.Owned, bool, error) {
	if e := ctx.Err(); e != nil {
		return nil, false, e
	}
	select {
	case r.operation <- struct{}{}:
		defer func() { <-r.operation }()
	case <-ctx.Done():
		return nil, false, ctx.Err()
	}
	r.mu.Lock()
	if r.stopping || r.consumed || r.failure != nil {
		r.mu.Unlock()
		return nil, true, ErrClosed
	}
	if e := r.owner.BeginCaptureLocked(); e != nil {
		r.mu.Unlock()
		return nil, false, e
	}
	r.checking = true
	id, e := Next32(&r.sequence)
	if e != nil {
		r.mu.Unlock()
		return r.captureFailure(ctx, e)
	}
	r.captureID = uint64(id)
	r.mu.Unlock()
	if e = ctx.Err(); e != nil {
		r.endCheck()
		return nil, false, e
	}
	flag := uint64(0)
	if rollback {
		flag = 1
	}
	reply, e := r.rpcContext(ctx, frame{kind: kindCaptureFence, value: uint64(id), generation: flag})
	if e != nil {
		var unsent *unsentControl
		if errors.As(e, &unsent) {
			r.endCheck()
			return nil, false, e
		}
		return r.captureFailure(ctx, e)
	}
	if reply.kind == kindRejected && (reply.value == 1 || reply.value == 2) {
		r.endCheck()
		code := "busy"
		if reply.value == 2 {
			code = "transaction_active"
		}
		return nil, false, &Rejected{code, string(reply.body)}
	}
	if reply.kind != kindFenced || reply.value != uint64(id) {
		return r.captureFailure(ctx, errors.New("invalid capture fence"))
	}
	r.mu.Lock()
	r.consumed = true
	r.mu.Unlock()
	r.capture.Request()
	reply, e = r.rpcContext(ctx, frame{kind: kindCaptureStop, value: uint64(id)})
	if e != nil {
		return r.captureFailure(ctx, e)
	}
	if reply.kind != kindStopAccepted || reply.value != uint64(id) {
		return r.captureFailure(ctx, errors.New("invalid capture kindStop acceptance"))
	}
	if e = ctx.Err(); e != nil {
		return r.captureFailure(ctx, e)
	}
	r.mu.Lock()
	r.stopAcked = true
	receipt := r.stopReceipt
	r.mu.Unlock()
	if receipt {
		r.resolve(nil)
	}
	r.stopIngress()
	if e = disposal.Wait(ctx, r.done); e != nil {
		return r.captureFailure(ctx, e)
	}
	if e = r.Failure(); e != nil {
		return r.captureFailure(ctx, e)
	}
	image, e := r.capture.TakeRoot(r.build)
	if e != nil {
		return r.captureFailure(ctx, e)
	}
	owned, e := stored.OwnRoot(image, r.build)
	if e != nil {
		// A failed ownership transfer must remain visible independently of eventual
		// physical execution cleanup. It cannot forgive an enclosing parent lease.
		r.mu.Lock()
		r.captureDebt = fmt.Errorf("captured root ownership: %w", e)
		debt := r.captureDebt
		r.mu.Unlock()
		return r.captureFailure(ctx, debt)
	}
	if e = r.disposer.Retry(ctx); e != nil {
		return owned, true, disposal.Retain(nil, e, r.disposer)
	}
	return owned, true, nil
}
