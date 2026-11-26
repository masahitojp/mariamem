package nativewire

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// settleFake simulates the host<->guest control/data protocol with explicit
// session phase, transaction status, ACK delivery, and fence rejection control.
type settleFake struct {
	mu           sync.Mutex
	phase        string
	status       uint64
	outstanding  uint64
	fences       atomic.Int32
	acksReceived atomic.Int32
	onFence      func(attempt int, f frame) (kind uint8, val uint64, body []byte, hold bool)
	holdFence    chan struct{}
	fenceSeen    chan int
	sendFn       func(frame)
	slot         uint32
	gen          uint64
	openedCh     chan key
	ackCh        chan uint64
}

func newSettleFake(phase string) *settleFake {
	return &settleFake{
		phase:     phase,
		fenceSeen: make(chan int, 16),
		openedCh:  make(chan key, 16),
		ackCh:     make(chan uint64, 16),
	}
}

func (f *settleFake) setPhase(p string) {
	f.mu.Lock()
	f.phase = p
	send := f.sendFn
	slot, gen := f.slot, f.gen
	f.mu.Unlock()
	if send != nil && gen != 0 {
		send(frame{kind: kindState, slot: slot, generation: gen, body: []byte(p)})
	}
}

func (f *settleFake) setPhaseSilent(p string) {
	f.mu.Lock()
	f.phase = p
	f.mu.Unlock()
}

func (f *settleFake) run(x Execution) <-chan error {
	done := make(chan error, 1)
	go func() {
		var failure error
		var writeMu sync.Mutex
		send := func(v frame) {
			v.epoch = x.Epoch
			writeMu.Lock()
			e := writeFrame(x.Output, v)
			writeMu.Unlock()
			if e != nil {
				failure = e
			}
		}
		f.mu.Lock()
		f.sendFn = send
		f.mu.Unlock()

		source := prepared.NewRootSource(true)
		if e := x.Capture.BindRootSource(source, "fake-guest"); e != nil {
			failure = e
		}
		send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})

		var captureStop frame
		stopped := false
		for {
			v, e := readFrame(x.Input)
			if e != nil {
				break
			}
			switch v.kind {
			case kindOpen:
				f.mu.Lock()
				f.slot = v.slot
				f.gen = v.generation
				ph := f.phase
				f.mu.Unlock()
				send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
				send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte(ph)})
				select {
				case f.openedCh <- key{v.slot, v.generation}:
				default:
				}
			case kindPeerEOF:
				send(frame{kind: kindRetired, slot: v.slot, generation: v.generation})
			case kindData:
				send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
			case kindAck:
				f.acksReceived.Add(1)
				f.mu.Lock()
				if f.outstanding > 0 {
					f.outstanding = 0
				}
				if f.phase == "flushing" {
					f.phase = "idle"
					send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
				}
				f.mu.Unlock()
				select {
				case f.ackCh <- v.value:
				default:
				}
			case kindStats:
				f.mu.Lock()
				payload, _ := json.Marshal(struct {
					Sessions []struct {
						Slot        uint32 `json:"slot"`
						Generation  uint64 `json:"generation"`
						Phase       string `json:"phase"`
						Status      uint64 `json:"status"`
						Outstanding uint64 `json:"outstanding"`
					} `json:"sessions"`
				}{
					Sessions: []struct {
						Slot        uint32 `json:"slot"`
						Generation  uint64 `json:"generation"`
						Phase       string `json:"phase"`
						Status      uint64 `json:"status"`
						Outstanding uint64 `json:"outstanding"`
					}{{
						Slot:        f.slot,
						Generation:  f.gen,
						Phase:       f.phase,
						Status:      f.status,
						Outstanding: f.outstanding,
					}},
				})
				f.mu.Unlock()
				send(frame{kind: kindStatsReply, request: v.request, body: payload})
			case kindCaptureFence:
				n := int(f.fences.Add(1))
				select {
				case f.fenceSeen <- n:
				default:
				}
				f.mu.Lock()
				cb := f.onFence
				hold := f.holdFence
				f.mu.Unlock()
				if cb != nil {
					k, val, body, shouldHold := cb(n, v)
					if shouldHold && hold != nil {
						<-hold
					}
					if k != 0 {
						send(frame{kind: k, request: v.request, value: val, body: body})
						continue
					}
				}
				f.mu.Lock()
				ph := f.phase
				st := f.status
				f.mu.Unlock()
				if ph != "idle" {
					send(frame{kind: kindRejected, request: v.request, value: 1, body: []byte("busy")})
				} else if v.generation == 0 && st&1 != 0 {
					send(frame{kind: kindRejected, request: v.request, value: 2, body: []byte("transaction_active")})
				} else {
					send(frame{kind: kindFenced, request: v.request, value: v.value})
				}
			case kindCaptureStop:
				captureStop = v
				send(frame{kind: kindStopAccepted, request: v.request, value: v.value})
				stopped = true
			case kindStop:
				stopped = true
			}
			if stopped {
				break
			}
		}
		if captureStop.kind == kindCaptureStop {
			send(frame{kind: kindCaptureStopped, request: captureStop.request, value: captureStop.value})
			if e := <-x.Approval; e == nil {
				if e := x.Capture.CompleteRoot(source, "fake-guest", []string{"."}, nil); e != nil {
					failure = e
				}
			}
		}
		done <- failure
	}()
	return done
}

func startSettleBackend(t *testing.T, f *settleFake) (*Backend, net.Conn) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: f.run, Build: "fake-guest"})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		cctx, ccancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer ccancel()
		_ = b.Close(cctx)
	})
	conn, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	// Wait until OPENED + initial STATE arrived so the session is active.
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		b.mu.Lock()
		n := len(b.sessions)
		b.mu.Unlock()
		f.mu.Lock()
		gen := f.gen
		f.mu.Unlock()
		if n == 1 && gen != 0 {
			break
		}
		time.Sleep(time.Millisecond)
	}
	return b, conn
}

func TestSnapshotHeapSettlesHeldAckBeforeFence(t *testing.T) {
	f := newSettleFake("flushing")
	f.outstanding = 7
	b, conn := startSettleBackend(t, f)

	ackEntered := make(chan struct{})
	releaseAck := make(chan struct{})
	b.mu.Lock()
	b.beforeAck = func(_ key, _ uint64) {
		close(ackEntered)
		<-releaseAck
	}
	b.mu.Unlock()

	// Deliver OK response bytes to client while guest is in FLUSHING.
	f.mu.Lock()
	f.sendFn(frame{kind: kindRaw, slot: f.slot, generation: f.gen, value: 0, body: []byte("OK-PKT!")})
	f.mu.Unlock()

	buf := make([]byte, 7)
	if _, err := io.ReadFull(conn, buf); err != nil {
		t.Fatal(err)
	}
	<-ackEntered

	waitCtx, stopWaiting := context.WithTimeout(context.Background(), 25*time.Millisecond)
	owned, consumed, err := b.SnapshotHeap(waitCtx, true)
	stopWaiting()
	if owned != nil || consumed || !errors.Is(err, context.DeadlineExceeded) || b.Failure() != nil {
		close(releaseAck)
		t.Fatalf("expected a non-consuming deadline before the fence: owned=%v consumed=%v err=%v backend failure=%v",
			owned != nil, consumed, err, b.Failure())
	}
	select {
	case <-f.fenceSeen:
		close(releaseAck)
		t.Fatal("Snapshot sent a fence while ACK was pending")
	default:
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	type res struct {
		owned    bool
		consumed bool
		err      error
	}
	done := make(chan res, 1)
	go func() {
		o, c, e := b.SnapshotHeap(ctx, true)
		if o != nil {
			_ = o.Close()
		}
		done <- res{o != nil, c, e}
	}()

	// Give SnapshotHeap time to block on waitPendingAcks; no fence should fail busy yet.
	time.Sleep(25 * time.Millisecond)
	select {
	case r := <-done:
		t.Fatalf("SnapshotHeap returned early while ACK was held: %+v", r)
	default:
	}

	close(releaseAck)
	r := <-done
	if !r.owned || !r.consumed || r.err != nil {
		t.Fatalf("expected SnapshotHeap to succeed after ACK release, got %+v", r)
	}
}

func TestSnapshotHeapSettlesPreemptedWriterWithPositiveOutBytes(t *testing.T) {
	f := newSettleFake("flushing")
	f.outstanding = 7
	b, conn := startSettleBackend(t, f)

	writerPaused := make(chan struct{})
	releaseWriter := make(chan struct{})
	busyObserved := make(chan struct{}, 1)
	b.mu.Lock()
	b.afterWriteBeforeRelease = func(_ key) {
		close(writerPaused)
		<-releaseWriter
	}
	b.afterBusyFence = func(attempt int) {
		if attempt == 1 {
			select {
			case busyObserved <- struct{}{}:
			default:
			}
		}
	}
	b.mu.Unlock()

	// Deliver OK packet to client while pausing writer BEFORE releaseOutputBytes/ackTarget,
	// so client has finished reading OK while host s.outBytes is still > 0!
	f.mu.Lock()
	f.sendFn(frame{kind: kindRaw, slot: f.slot, generation: f.gen, value: 0, body: []byte("OK-PKT!")})
	f.mu.Unlock()

	buf := make([]byte, 7)
	if _, err := io.ReadFull(conn, buf); err != nil {
		t.Fatal(err)
	}
	<-writerPaused
	if !b.hasAnyQueuedOutput() {
		t.Fatal("expected s.outBytes > 0 while writer is paused after Write and before releaseOutputBytes")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	type res struct {
		owned    bool
		consumed bool
		err      error
	}
	done := make(chan res, 1)
	go func() {
		o, c, e := b.SnapshotHeap(ctx, true)
		if o != nil {
			_ = o.Close()
		}
		done <- res{o != nil, c, e}
	}()

	// Wait until fence #1 returned busy while outBytes was still > 0.
	select {
	case <-busyObserved:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for first busy fence")
	}
	if !b.hasAnyQueuedOutput() {
		t.Fatal("expected outBytes to still be > 0 before releasing writer")
	}

	// Release writer promptly (simulating preempted writer resuming); the exact
	// same SnapshotHeap call must settle outBytes -> ACK -> IDLE and succeed.
	close(releaseWriter)
	r := <-done
	if !r.owned || !r.consumed || r.err != nil {
		t.Fatalf("expected SnapshotHeap to succeed after preempted writer resumed, got %+v", r)
	}
}

func TestSnapshotHeapRetriesWhenIdleImmediatelyAfterBusyRejection(t *testing.T) {
	f := newSettleFake("flushing")
	b, _ := startSettleBackend(t, f)

	// Fence #1 sees FLUSHING -> rejects busy, then guest becomes IDLE before STATS!
	b.mu.Lock()
	b.afterBusyFence = func(attempt int) {
		if attempt == 1 {
			f.setPhaseSilent("idle")
		}
	}
	b.mu.Unlock()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	owned, consumed, err := b.SnapshotHeap(ctx, true)
	if err != nil || !consumed || owned == nil {
		t.Fatalf("expected retry after post-busy IDLE transition to succeed, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	_ = owned.Close()
	if got := f.fences.Load(); got != 2 {
		t.Fatalf("expected 2 fence attempts, got %d", got)
	}
}

func TestSnapshotHeapRejectsBusyImmediatelyOnLongSQL(t *testing.T) {
	f := newSettleFake("executing")
	b, _ := startSettleBackend(t, f)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	start := time.Now()
	owned, consumed, err := b.SnapshotHeap(ctx, true)
	elapsed := time.Since(start)
	var rej *Rejected
	if owned != nil || consumed || !errors.As(err, &rej) || rej.Code != "busy" {
		t.Fatalf("expected non-consuming busy on executing SQL, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	if elapsed > 150*time.Millisecond {
		t.Fatalf("long SQL busy rejection took too long: %v", elapsed)
	}
	if f.fences.Load() != 1 {
		t.Fatalf("expected single fence attempt for long SQL without output, got %d", f.fences.Load())
	}
	// Source remains usable after non-consuming busy rejection.
	f.setPhase("idle")
	owned, consumed, err = b.SnapshotHeap(ctx, true)
	if err != nil || !consumed || owned == nil {
		t.Fatalf("source unusable after busy rejection: owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	_ = owned.Close()
}

func TestSnapshotHeapRejectsBusyPromptlyMidMultiResult(t *testing.T) {
	f := newSettleFake("executing")
	b, conn := startSettleBackend(t, f)

	// Deliver result set 1 and ACK it while session stays in "executing" (computing result set 2).
	f.mu.Lock()
	f.sendFn(frame{kind: kindRaw, slot: f.slot, generation: f.gen, value: 0, body: []byte("RESULT-1")})
	f.mu.Unlock()
	buf := make([]byte, 8)
	if _, err := io.ReadFull(conn, buf); err != nil {
		t.Fatal(err)
	}
	<-f.ackCh

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	start := time.Now()
	owned, consumed, err := b.SnapshotHeap(ctx, true)
	elapsed := time.Since(start)
	var rej *Rejected
	if owned != nil || consumed || !errors.As(err, &rej) || rej.Code != "busy" {
		t.Fatalf("expected non-consuming busy mid-multi-result, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	if elapsed > 200*time.Millisecond {
		t.Fatalf("mid-multi-result busy rejection waited too long: %v", elapsed)
	}
}

func TestSnapshotHeapRejectsBusyImmediatelyOnStalledHostWrite(t *testing.T) {
	f := newSettleFake("flushing")
	f.outstanding = 16
	b, _ := startSettleBackend(t, f)

	// Push output to the session without reading from net.Pipe() client conn,
	// so relay's c.Write(b) blocks with s.outBytes > 0!
	f.mu.Lock()
	f.sendFn(frame{kind: kindRaw, slot: f.slot, generation: f.gen, value: 0, body: []byte("STALLED-RESPONSE")})
	f.mu.Unlock()

	deadline := time.Now().Add(2 * time.Second)
	for !b.hasAnyQueuedOutput() && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if !b.hasAnyQueuedOutput() {
		t.Fatal("expected stalled host output queue to be non-empty")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	start := time.Now()
	owned, consumed, err := b.SnapshotHeap(ctx, true)
	elapsed := time.Since(start)
	var rej *Rejected
	if owned != nil || consumed || !errors.As(err, &rej) || rej.Code != "busy" {
		t.Fatalf("expected non-consuming busy on stalled host Write, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	if elapsed > 150*time.Millisecond {
		t.Fatalf("stalled host Write busy rejection took too long: %v", elapsed)
	}
}

func TestSnapshotHeapPreservesTransactionActiveAfterFlushSettle(t *testing.T) {
	f := newSettleFake("flushing")
	f.status = 1 // SERVER_STATUS_IN_TRANS
	b, _ := startSettleBackend(t, f)

	b.mu.Lock()
	b.afterBusyFence = func(attempt int) {
		if attempt == 1 {
			f.setPhase("idle")
		}
	}
	b.mu.Unlock()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	owned, consumed, err := b.SnapshotHeap(ctx, false)
	var rej *Rejected
	if owned != nil || consumed || !errors.As(err, &rej) || rej.Code != "transaction_active" {
		t.Fatalf("expected non-consuming transaction_active, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
}

func TestSnapshotHeapCancelAfterExplicitBusyPreservesSourceDB(t *testing.T) {
	f := newSettleFake("flushing")
	b, _ := startSettleBackend(t, f)

	ctx, cancel := context.WithCancel(context.Background())
	b.mu.Lock()
	b.afterBusyFence = func(attempt int) {
		if attempt == 1 {
			cancel()
		}
	}
	b.mu.Unlock()

	owned, consumed, err := b.SnapshotHeap(ctx, true)
	if owned != nil || consumed || !errors.Is(err, context.Canceled) {
		t.Fatalf("expected non-consuming context.Canceled after explicit busy rejection, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	if b.Failure() != nil {
		t.Fatalf("source DB became failed after pre-retry cancel: %v", b.Failure())
	}

	// Verify source DB remains completely usable: can dial a new session and take SnapshotHeap.
	b.mu.Lock()
	b.afterBusyFence = nil
	b.mu.Unlock()
	f.setPhase("idle")

	okCtx, okCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer okCancel()
	// Drain initial session open notification.
	select {
	case <-f.openedCh:
	default:
	}
	c2, err := b.DialContext(okCtx)
	if err != nil {
		t.Fatalf("DialContext failed after non-consuming cancel: %v", err)
	}
	<-f.openedCh
	_ = c2.Close()
	// Wait for c2 to retire cleanly before taking SnapshotHeap.
	deadline := time.Now().Add(2 * time.Second)
	for b.Active() > 1 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}

	owned, consumed, err = b.SnapshotHeap(okCtx, true)
	if err != nil || !consumed || owned == nil {
		t.Fatalf("subsequent SnapshotHeap failed on preserved source DB: owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	_ = owned.Close()
}

func TestSnapshotHeapCancelDuringInFlightFenceRemainsConsuming(t *testing.T) {
	f := newSettleFake("idle")
	f.holdFence = make(chan struct{})
	f.onFence = func(_ int, v frame) (uint8, uint64, []byte, bool) {
		return kindFenced, v.value, nil, true
	}
	b, _ := startSettleBackend(t, f)

	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		<-f.fenceSeen
		cancel()
	}()

	owned, consumed, err := b.SnapshotHeap(ctx, true)
	close(f.holdFence)
	if owned != nil || !consumed || !errors.Is(err, context.Canceled) {
		t.Fatalf("expected uncertain in-flight fence cancel to remain consuming, got owned=%v consumed=%v err=%v", owned, consumed, err)
	}
}

func TestSnapshotHeapFailureReturnsBeforeGuestDisposal(t *testing.T) {
	for _, stopAccepted := range []bool{false, true} {
		name := "fence_reply_pending"
		if stopAccepted {
			name = "stop_accepted"
		}
		t.Run(name, func(t *testing.T) {
			cause := errors.New("injected guest failure")
			waiting := make(chan struct{})
			release := make(chan struct{})
			finishGuest := sync.OnceFunc(func() { close(release) })
			defer finishGuest()

			var notifyFailure func(error)
			runner := func(x Execution) <-chan error {
				notifyFailure = x.Failure
				done := make(chan error, 1)
				go func() {
					reply := func(f frame) error {
						f.epoch = x.Epoch
						return writeFrame(x.Output, f)
					}
					err := reply(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
					if err == nil {
						var fence frame
						fence, err = readFrame(x.Input)
						if err == nil && stopAccepted {
							err = reply(frame{kind: kindFenced, request: fence.request, value: fence.value})
							if err == nil {
								var stop frame
								stop, err = readFrame(x.Input)
								if err == nil {
									err = reply(frame{kind: kindStopAccepted, request: stop.request, value: stop.value})
								}
							}
						}
					}
					if err == nil {
						close(waiting)
						<-release
						err = cause
					}
					done <- err
				}()
				return done
			}

			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			b, err := Start(ctx, Config{Runner: runner, Build: "fake-guest"})
			if err != nil {
				t.Fatal(err)
			}
			type result struct {
				consumed bool
				err      error
			}
			results := make(chan result, 1)
			go func() {
				backing, consumed, err := b.SnapshotHeap(context.Background(), true)
				if backing != nil {
					_ = backing.Close()
					err = errors.New("failed Snapshot unexpectedly returned backing")
				}
				results <- result{consumed, err}
			}()
			waitFor(t, waiting)
			if stopAccepted {
				for {
					b.mu.Lock()
					stopping := b.stopAcked && b.stopping
					b.mu.Unlock()
					if stopping {
						break
					}
					select {
					case <-ctx.Done():
						t.Fatal("host did not enter the stop completion wait")
					case <-time.After(time.Millisecond):
					}
				}
			}
			notifyFailure(cause)
			select {
			case got := <-results:
				owners := disposal.Owners(got.err)
				if !got.consumed || !errors.Is(got.err, cause) || len(owners) != 1 || owners[0].Complete() {
					t.Fatalf("expected consuming failure with a pending owner: %+v", got)
				}
			case <-ctx.Done():
				t.Fatal("Snapshot did not return before guest completion")
			}
			finishGuest()
			waitFor(t, b.disposer.Done())
		})
	}
}
