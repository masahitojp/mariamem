package nativewire

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

const (
	flushingSettleBudget = 500 * time.Millisecond
	writeDrainBudget     = 50 * time.Millisecond
	tailExecSettleBudget = 15 * time.Millisecond
	maxIdleFenceRetries  = 4
)

type busySettleAction uint8

const (
	settleRejectBusy busySettleAction = iota
	settleRetryNow
	settleWaitWriteDrain
	settleWaitFlushing
	settleWaitTailExec
)

// Rejected is a definitive, non-consuming guest capture rejection. Public
// adapters map its Code to the existing busy/transaction errors.
type Rejected struct {
	Code    string
	Message string
}

func (e *Rejected) Error() string { return e.Message }

func (r *Backend) captureFailure(cause error) (*stored.Owned, bool, error) {
	r.mu.Lock()
	r.consumed = true
	r.checking = false
	r.owner.EndCaptureLocked()
	r.mu.Unlock()
	r.fail(cause)
	// The failure is final even if the guest still owns resources.
	e := r.disposer.Probe()
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

type sessionSettleSnapshot struct {
	s            *session
	ackPending   bool
	cmdAcked     bool
	queuedOutput bool
}

func (r *Backend) snapshotSessionsForSettle() (map[key]sessionSettleSnapshot, chan struct{}, bool) {
	r.mu.Lock()
	if r.activityChanged == nil {
		r.activityChanged = make(chan struct{})
	}
	ch := r.activityChanged
	if len(r.sessions) == 0 {
		r.mu.Unlock()
		return nil, ch, false
	}
	out := make(map[key]sessionSettleSnapshot, len(r.sessions))
	for k, s := range r.sessions {
		out[k] = sessionSettleSnapshot{
			s:          s,
			ackPending: s.ackSent < s.ackTarget,
			cmdAcked:   s.cmdAcked,
		}
	}
	r.mu.Unlock()
	for k, snap := range out {
		snap.queuedOutput = snap.s.hasQueuedOutput()
		out[k] = snap
	}
	return out, ch, true
}

func (r *Backend) hasAnyQueuedOutput() bool {
	r.mu.Lock()
	list := make([]*session, 0, len(r.sessions))
	for _, s := range r.sessions {
		list = append(list, s)
	}
	r.mu.Unlock()
	for _, s := range list {
		if s.hasQueuedOutput() {
			return true
		}
	}
	return false
}

// waitPendingAcks waits while any session has already delivered response bytes
// via conn.Write and has not yet finished sending its corresponding kindAck.
// Never waits when any session still has queued/stalled output awaiting Write.
func (r *Backend) waitPendingAcks(ctx context.Context) error {
	for {
		if e := ctx.Err(); e != nil {
			return e
		}
		snaps, ch, ok := r.snapshotSessionsForSettle()
		if !ok {
			return nil
		}
		anyPending := false
		for _, snap := range snaps {
			if snap.s.hasQueuedOutput() {
				return nil
			}
			if snap.ackPending {
				anyPending = true
			}
		}
		if !anyPending {
			return nil
		}
		select {
		case <-ch:
		case <-r.failed:
			if f := r.Failure(); f != nil {
				return f
			}
			return ErrClosed
		case <-r.done:
			return ErrClosed
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (r *Backend) classifyBusySettle(st guestStats, snaps map[key]sessionSettleSnapshot) busySettleAction {
	anyQueuedOutput := false
	for _, snap := range snaps {
		if snap.queuedOutput {
			anyQueuedOutput = true
		}
	}
	anyNonIdle := false
	anyFlushing := false
	anyTailExec := false
	for _, gs := range st.Sessions {
		if gs.Phase == "idle" {
			continue
		}
		anyNonIdle = true
		snap, ok := snaps[key{gs.Slot, gs.Generation}]
		switch gs.Phase {
		case "flushing":
			anyFlushing = true
		case "executing":
			if !ok || (!snap.queuedOutput && !snap.ackPending && !snap.cmdAcked) {
				return settleRejectBusy
			}
			anyTailExec = true
		default:
			return settleRejectBusy
		}
	}
	if !anyNonIdle {
		return settleRetryNow
	}
	if anyQueuedOutput {
		return settleWaitWriteDrain
	}
	if anyTailExec {
		return settleWaitTailExec
	}
	if anyFlushing {
		return settleWaitFlushing
	}
	return settleRejectBusy
}

// SnapshotHeap always asks the guest's final atomic fence. Busy is merely an
// advisory STATE cache and never authorizes capture. After acceptance every
// error is consuming, even if physical join remains pending.
func (r *Backend) SnapshotHeap(ctx context.Context, rollback bool) (*stored.Owned, bool, error) {
	ctx, finish := timing.Begin(ctx, "snapshot_capture")
	defer finish()
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
		return r.captureFailure(e)
	}
	r.captureID = uint64(id)
	r.mu.Unlock()
	flag := uint64(0)
	if rollback {
		flag = 1
	}

	var flushDeadline time.Time
	var writeDrainDeadline time.Time
	var execDeadline time.Time
	idleRetries := 0
	attempt := 0
	for {
		if e := r.waitPendingAcks(ctx); e != nil {
			r.endCheck()
			return nil, false, e
		}
		if e = ctx.Err(); e != nil {
			r.endCheck()
			return nil, false, e
		}
		attempt++
		reply, e := r.rpcContext(ctx, frame{kind: kindCaptureFence, value: uint64(id), generation: flag})
		if e != nil {
			var unsent *unsentControl
			if errors.As(e, &unsent) {
				r.endCheck()
				return nil, false, e
			}
			return r.captureFailure(e)
		}
		if reply.kind == kindRejected && reply.value == 2 {
			r.endCheck()
			return nil, false, &Rejected{"transaction_active", string(reply.body)}
		}
		if reply.kind == kindRejected && reply.value == 1 {
			r.mu.Lock()
			hook := r.afterBusyFence
			r.mu.Unlock()
			if hook != nil {
				hook(attempt)
			}
			snaps, actCh, hasSessions := r.snapshotSessionsForSettle()
			if !hasSessions {
				r.endCheck()
				return nil, false, &Rejected{"busy", string(reply.body)}
			}
			if e := ctx.Err(); e != nil {
				r.endCheck()
				return nil, false, e
			}
			st, stErr := r.queryStats(ctx)
			if stErr != nil {
				if ctx.Err() != nil {
					r.endCheck()
					return nil, false, ctx.Err()
				}
				if f := r.Failure(); f != nil {
					return r.captureFailure(f)
				}
				r.endCheck()
				return nil, false, &Rejected{"busy", string(reply.body)}
			}
			// Re-check host session queued-output / ACK state after STATS too.
			snapsAfter, _, _ := r.snapshotSessionsForSettle()
			if snapsAfter != nil {
				snaps = snapsAfter
			}
			switch r.classifyBusySettle(st, snaps) {
			case settleRetryNow:
				idleRetries++
				if idleRetries > maxIdleFenceRetries {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				continue
			case settleWaitWriteDrain:
				now := time.Now()
				if writeDrainDeadline.IsZero() {
					writeDrainDeadline = now.Add(writeDrainBudget)
				}
				if !now.Before(writeDrainDeadline) {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				timer := time.NewTimer(time.Until(writeDrainDeadline))
				expired := false
				select {
				case <-actCh:
					timer.Stop()
				case <-timer.C:
					expired = true
				case <-r.failed:
					timer.Stop()
					if f := r.Failure(); f != nil {
						return r.captureFailure(f)
					}
					r.endCheck()
					return nil, false, ErrClosed
				case <-r.done:
					timer.Stop()
					r.endCheck()
					return nil, false, ErrClosed
				case <-ctx.Done():
					timer.Stop()
					r.endCheck()
					return nil, false, ctx.Err()
				}
				if expired && r.hasAnyQueuedOutput() {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				continue
			case settleWaitFlushing:
				now := time.Now()
				if flushDeadline.IsZero() {
					flushDeadline = now.Add(flushingSettleBudget)
				}
				if !now.Before(flushDeadline) {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				wait := time.Until(flushDeadline)
				if wait > 5*time.Millisecond {
					wait = 5 * time.Millisecond
				}
				timer := time.NewTimer(wait)
				select {
				case <-actCh:
					timer.Stop()
				case <-timer.C:
				case <-r.failed:
					timer.Stop()
					if f := r.Failure(); f != nil {
						return r.captureFailure(f)
					}
					r.endCheck()
					return nil, false, ErrClosed
				case <-r.done:
					timer.Stop()
					r.endCheck()
					return nil, false, ErrClosed
				case <-ctx.Done():
					timer.Stop()
					r.endCheck()
					return nil, false, ctx.Err()
				}
				if r.hasAnyQueuedOutput() {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				continue
			case settleWaitTailExec:
				now := time.Now()
				if execDeadline.IsZero() {
					execDeadline = now.Add(tailExecSettleBudget)
				}
				if !now.Before(execDeadline) {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				timer := time.NewTimer(time.Until(execDeadline))
				expired := false
				select {
				case <-actCh:
					timer.Stop()
				case <-timer.C:
					expired = true
				case <-r.failed:
					timer.Stop()
					if f := r.Failure(); f != nil {
						return r.captureFailure(f)
					}
					r.endCheck()
					return nil, false, ErrClosed
				case <-r.done:
					timer.Stop()
					r.endCheck()
					return nil, false, ErrClosed
				case <-ctx.Done():
					timer.Stop()
					r.endCheck()
					return nil, false, ctx.Err()
				}
				if expired || r.hasAnyQueuedOutput() {
					r.endCheck()
					return nil, false, &Rejected{"busy", string(reply.body)}
				}
				continue
			default:
				r.endCheck()
				return nil, false, &Rejected{"busy", string(reply.body)}
			}
		}
		if reply.kind != kindFenced || reply.value != uint64(id) {
			return r.captureFailure(errors.New("invalid capture fence"))
		}
		break
	}
	r.mu.Lock()
	r.consumed = true
	r.mu.Unlock()
	r.capture.Request()
	reply, e := r.rpcContext(ctx, frame{kind: kindCaptureStop, value: uint64(id)})
	if e != nil {
		return r.captureFailure(e)
	}
	if reply.kind != kindStopAccepted || reply.value != uint64(id) {
		return r.captureFailure(errors.New("invalid capture kindStop acceptance"))
	}
	if e = ctx.Err(); e != nil {
		return r.captureFailure(e)
	}
	r.mu.Lock()
	r.stopAcked = true
	receipt := r.stopReceipt
	r.mu.Unlock()
	if receipt {
		r.resolve(nil)
	}
	r.stopIngress()
	select {
	case <-r.done:
	default:
		select {
		case <-r.done:
		case <-r.failed:
			return r.captureFailure(r.Failure())
		case <-ctx.Done():
			return r.captureFailure(ctx.Err())
		}
	}
	if e = r.Failure(); e != nil {
		return r.captureFailure(e)
	}
	image, e := r.capture.TakeRoot(r.build)
	if e != nil {
		return r.captureFailure(e)
	}
	owned, e := stored.OwnRoot(image, r.build)
	for key, v := range image.Counts() {
		timing.Work(ctx, "root/"+key+"/read", v.Read, 0)
		timing.Work(ctx, "root/"+key+"/copy", v.Copy, 0)
		timing.Work(ctx, "root/"+key+"/hash", v.Hash, 0)
		timing.Work(ctx, "root/"+key+"/zero", v.Zero, v.Metadata)
	}
	if e != nil {
		// A failed ownership transfer must remain visible independently of eventual
		// physical execution cleanup. It cannot forgive an enclosing parent lease.
		r.mu.Lock()
		r.captureDebt = fmt.Errorf("captured root ownership: %w", e)
		debt := r.captureDebt
		r.mu.Unlock()
		return r.captureFailure(debt)
	}
	if e = r.disposer.Retry(ctx); e != nil {
		return owned, true, disposal.Retain(nil, e, r.disposer)
	}
	return owned, true, nil
}
