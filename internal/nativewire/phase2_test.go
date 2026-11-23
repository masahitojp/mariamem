package nativewire

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/timing"
)

func TestBytePipeWrapAroundAndClose(t *testing.T) {
	r, w := newBytePipe()
	payload := bytes.Repeat([]byte("0123456789abcdef"), 4096) // 64 KiB > 16 KiB ring
	var wg sync.WaitGroup
	wg.Add(1)
	var writeErr error
	go func() {
		defer wg.Done()
		for off := 0; off < len(payload); {
			step := 333
			if off+step > len(payload) {
				step = len(payload) - off
			}
			n, err := w.Write(payload[off : off+step])
			if err != nil {
				writeErr = err
				return
			}
			off += n
		}
		writeErr = w.Close()
	}()
	got, err := io.ReadAll(r)
	wg.Wait()
	if err != nil || writeErr != nil {
		t.Fatalf("read=%v write=%v", err, writeErr)
	}
	if !bytes.Equal(got, payload) {
		t.Fatalf("payload mismatch: got=%d want=%d", len(got), len(payload))
	}

	// Closing reader unblocks a blocked writer with ErrClosedPipe.
	r2, w2 := newBytePipe()
	blocked := make(chan error, 1)
	go func() {
		_, err := w2.Write(make([]byte, 32*1024))
		blocked <- err
	}()
	time.Sleep(5 * time.Millisecond)
	_ = r2.Close()
	select {
	case err := <-blocked:
		if !errors.Is(err, io.ErrClosedPipe) {
			t.Fatalf("want ErrClosedPipe, got %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("writer did not unblock on reader close")
	}
	_ = w2.Close()
}

func TestDisconnectStateAndCloseWithStopped(t *testing.T) {
	f := newFake()
	b, _ := startFake(t, f)

	active, ch, _, _ := b.DisconnectState()
	if active != 0 || ch == nil {
		t.Fatalf("initial DisconnectState: active=%d ch=%v", active, ch)
	}

	c, err := b.DialContext(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	nextOpen(t, f)

	active, ch, _, _ = b.DisconnectState()
	if active != 1 || ch == nil {
		t.Fatalf("active DisconnectState: active=%d ch=%v", active, ch)
	}
	_ = c.Close()
	waitFor(t, ch)
	active, _, _, _ = b.DisconnectState()
	if active != 0 {
		t.Fatalf("after close active=%d", active)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	stopped := make(chan error, 1)
	if err := b.CloseWithStopped(ctx, func(e error) { stopped <- e }); err != nil {
		t.Fatal(err)
	}
	select {
	case e := <-stopped:
		if e != nil {
			t.Fatalf("stopped err: %v", e)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("CloseWithStopped did not invoke callback")
	}
}

func TestSnapshotCaptureTimingTrace(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	f := newFake()
	b, _ := startFake(t, f)
	var traces []timing.Trace
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	ctx = timing.WithRecorder(ctx, func(tr timing.Trace) { traces = append(traces, tr) })

	owned, consumed, err := b.SnapshotHeap(ctx, false)
	if err != nil || !consumed || owned == nil {
		t.Fatalf("SnapshotHeap: owned=%v consumed=%v err=%v", owned, consumed, err)
	}
	defer owned.Close()

	foundCapture := false
	for _, tr := range traces {
		if tr.Operation == "snapshot_capture" {
			foundCapture = true
		}
	}
	if !foundCapture {
		t.Fatalf("missing snapshot_capture trace: %+v", traces)
	}
}

// keepFakeRuntime simulates the guest wire protocol for SnapshotKeep unit tests:
// responds to STATS, HOLD, and minimal MySQL handshake + COM_QUERY on the private session.
type keepFakeRuntime struct {
	statsBody   string
	xaRows      int
	ftwrlErrno  uint16
	failUnhold  bool
	rootCut     atomic.Bool
	holdCalls   atomic.Int32
	unholdCalls atomic.Int32
	sqlQueries  []string
	mu          sync.Mutex
}

func mysqlPkt(seq byte, payload []byte) []byte {
	out := make([]byte, 4+len(payload))
	out[0], out[1], out[2], out[3] = byte(len(payload)), byte(len(payload)>>8), byte(len(payload)>>16), seq
	copy(out[4:], payload)
	return out
}

func (k *keepFakeRuntime) run(x Execution) <-chan error {
	done := make(chan error, 1)
	go func() {
		source := prepared.NewRootSource(true)
		_ = x.Capture.BindRootSource(source, "fake-keep")
		x.Capture.SetKeep(func() (*prepared.Root, error) {
			k.rootCut.Store(true)
			var c prepared.Capture
			if err := c.BindRootSource(source, "fake-keep"); err != nil {
				return nil, err
			}
			c.Request()
			if err := c.CompleteRoot(source, "fake-keep", []string{"."}, nil); err != nil {
				return nil, err
			}
			return c.TakeRoot("fake-keep")
		})
		send := func(v frame) {
			v.epoch = x.Epoch
			_ = writeFrame(x.Output, v)
		}
		send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
		seenAuth := map[uint32]bool{}
		retired := map[key]bool{}
		retireOnce := func(slot uint32, gen uint64) {
			k := key{slot, gen}
			if retired[k] {
				return
			}
			retired[k] = true
			delete(seenAuth, slot)
			send(frame{kind: kindRetired, slot: slot, generation: gen})
		}
		for {
			v, err := readFrame(x.Input)
			if err != nil {
				break
			}
			switch v.kind {
			case kindStats:
				body := k.statsBody
				if body == "" {
					body = `{"sessions":[]}`
				}
				send(frame{kind: kindStatsReply, request: v.request, body: []byte(body)})
			case kindHold:
				if v.value != 0 {
					k.holdCalls.Add(1)
				} else {
					k.unholdCalls.Add(1)
					if k.failUnhold {
						if x.Stopped != nil {
							x.Stopped(errors.New("lost HOLD=0 reply"))
						}
						done <- errors.New("lost HOLD=0 reply")
						return
					}
				}
				send(frame{kind: kindReply, request: v.request, slot: v.slot, generation: v.generation})
			case kindOpen:
				send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
				send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
				// Send minimal MySQL greeting packet (seq 0)
				send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(0, []byte{0x0a, '1', '2', 0})})
			case kindData:
				send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
				if len(v.body) < 4 {
					continue
				}
				payload := v.body[4:]
				if !seenAuth[v.slot] {
					seenAuth[v.slot] = true
					// OK packet (seq 2)
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(2, []byte{0x00, 0, 0, 2, 0, 0, 0})})
					continue
				}
				if len(payload) == 0 {
					continue
				}
				if payload[0] == 0x01 { // COM_QUIT
					retireOnce(v.slot, v.generation)
					continue
				}
				if payload[0] == 0x03 { // COM_QUERY
					q := string(payload[1:])
					k.mu.Lock()
					k.sqlQueries = append(k.sqlQueries, q)
					k.mu.Unlock()
					if q == "XA RECOVER" {
						var resp bytes.Buffer
						resp.Write(mysqlPkt(1, []byte{0x01})) // 1 col
						resp.Write(mysqlPkt(2, []byte{0x01, 'x'}))
						resp.Write(mysqlPkt(3, []byte{0xfe, 0, 0, 2, 0}))
						seq := byte(4)
						for i := 0; i < k.xaRows; i++ {
							resp.Write(mysqlPkt(seq, []byte{0x01, 'a'}))
							seq++
						}
						resp.Write(mysqlPkt(seq, []byte{0xfe, 0, 0, 2, 0}))
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: resp.Bytes()})
						continue
					}
					if q == "FLUSH TABLES WITH READ LOCK" && k.ftwrlErrno != 0 {
						ep := make([]byte, 9+len("lock timeout"))
						ep[0] = 0xff
						binary.LittleEndian.PutUint16(ep[1:3], k.ftwrlErrno)
						copy(ep[3:9], "#HY000")
						copy(ep[9:], "lock timeout")
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(1, ep)})
						continue
					}
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(1, []byte{0x00, 0, 0, 2, 0, 0, 0})})
				}
			case kindPeerEOF:
				retireOnce(v.slot, v.generation)
			case kindStop:
				if x.Stopped != nil {
					x.Stopped(nil)
				}
				done <- nil
				return
			}
		}
		if x.Stopped != nil {
			x.Stopped(nil)
		}
		done <- nil
	}()
	return done
}

func TestSnapshotKeepRejectionsAndTimingMarks(t *testing.T) {
	t.Run("active_transaction_rejected", func(t *testing.T) {
		k := &keepFakeRuntime{statsBody: `{"sessions":[{"slot":0,"generation":1,"phase":"idle","status":1}]}`}
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		b, err := Start(ctx, Config{Runner: k.run, Build: "fake-keep"})
		if err != nil {
			t.Fatal(err)
		}
		defer b.Close(ctx)
		owned, err := b.SnapshotKeep(ctx)
		var rej *Rejected
		if owned != nil || !errors.As(err, &rej) || rej.Code != "transaction_active" {
			t.Fatalf("want transaction_active rejection, got owned=%v err=%v", owned, err)
		}
	})

	t.Run("xa_recover_rejected", func(t *testing.T) {
		k := &keepFakeRuntime{xaRows: 1}
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		b, err := Start(ctx, Config{Runner: k.run, Build: "fake-keep"})
		if err != nil {
			t.Fatal(err)
		}
		defer b.Close(ctx)
		owned, err := b.SnapshotKeep(ctx)
		var rej *Rejected
		if owned != nil || !errors.As(err, &rej) || rej.Code != "transaction_active" {
			t.Fatalf("want transaction_active for XA, got owned=%v err=%v", owned, err)
		}
	})

	t.Run("ftwrl_lock_wait_timeout_rejected_busy", func(t *testing.T) {
		k := &keepFakeRuntime{ftwrlErrno: errLockWaitTimeout}
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		b, err := Start(ctx, Config{Runner: k.run, Build: "fake-keep"})
		if err != nil {
			t.Fatal(err)
		}
		defer b.Close(ctx)
		owned, err := b.SnapshotKeep(ctx)
		var rej *Rejected
		if owned != nil || !errors.As(err, &rej) || rej.Code != "busy" {
			t.Fatalf("want busy for FTWRL 1205, got owned=%v err=%v", owned, err)
		}
	})

	t.Run("success_holds_sessions_and_emits_timing", func(t *testing.T) {
		t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
		k := &keepFakeRuntime{}
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		b, err := Start(ctx, Config{Runner: k.run, Build: "fake-keep"})
		if err != nil {
			t.Fatal(err)
		}
		defer b.Close(ctx)
		b.capture.SetKeep(func() (*prepared.Root, error) {
			src := prepared.NewRootSource(true)
			var c prepared.Capture
			if err := c.BindRootSource(src, "fake-keep"); err != nil {
				return nil, err
			}
			c.Request()
			if err := c.CompleteRoot(src, "fake-keep", []string{"."}, nil); err != nil {
				return nil, err
			}
			return c.TakeRoot("fake-keep")
		})

		// Attach one idle external session so HOLD/UNHOLD is exercised.
		ext, err := b.DialContext(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer ext.Close()
		// Wait until session reaches idle.
		deadline := time.Now().Add(2 * time.Second)
		for b.Busy() && time.Now().Before(deadline) {
			time.Sleep(time.Millisecond)
		}

		var gotTrace timing.Trace
		recCtx := timing.WithRecorder(ctx, func(tr timing.Trace) {
			if tr.Operation == "snapshot_keep" {
				gotTrace = tr
			}
		})
		owned, err := b.SnapshotKeep(recCtx)
		if err != nil || owned == nil {
			t.Fatalf("SnapshotKeep failed: owned=%v err=%v", owned, err)
		}
		defer owned.Close()

		if k.holdCalls.Load() < 1 || k.unholdCalls.Load() < 1 {
			t.Fatalf("expected HOLD/UNHOLD calls, got hold=%d unhold=%d", k.holdCalls.Load(), k.unholdCalls.Load())
		}
		marks := map[string]bool{}
		for _, ev := range gotTrace.Events {
			marks[ev.Name] = true
		}
		for _, want := range []string{"sessions_quiesced", "tables_flushed", "engine_checkpointed", "files_cut"} {
			if !marks[want] {
				t.Fatalf("missing timing mark %q in %+v", want, gotTrace.Events)
			}
		}
	})
}

// P2 regression: if ctx is canceled after the guest applies HOLD=1 but before
// the host receives REPLY, SnapshotKeep must still send HOLD=0 so subsequent
// SQL on that existing session completes without deadlocking.
func TestSnapshotKeepCancelDuringHoldUnblocksExistingSession(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	holdApplied := make(chan struct{})
	var holdAppliedOnce sync.Once
	var unholdCount atomic.Int32
	var mu sync.Mutex
	heldSlots := map[uint32]bool{}
	holdCV := sync.NewCond(&mu)

	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			source := prepared.NewRootSource(true)
			_ = x.Capture.BindRootSource(source, "fake-hold-cancel")
			send := func(v frame) {
				v.epoch = x.Epoch
				_ = writeFrame(x.Output, v)
			}
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
			seenAuth := map[uint32]bool{}
			retired := map[key]bool{}
			retireOnce := func(slot uint32, gen uint64) {
				k := key{slot, gen}
				if retired[k] {
					return
				}
				retired[k] = true
				send(frame{kind: kindRetired, slot: slot, generation: gen})
			}
			for {
				v, err := readFrame(x.Input)
				if err != nil {
					break
				}
				switch v.kind {
				case kindOpen:
					send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
					send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(0, []byte{0x0a, '1', '2', 0})})
				case kindHold:
					if v.value != 0 {
						mu.Lock()
						heldSlots[v.slot] = true
						mu.Unlock()
						// Deliberately withhold REPLY for HOLD=1 to force the cancel race.
						holdAppliedOnce.Do(func() { close(holdApplied) })
					} else {
						unholdCount.Add(1)
						mu.Lock()
						heldSlots[v.slot] = false
						holdCV.Broadcast()
						mu.Unlock()
						send(frame{kind: kindReply, request: v.request, slot: v.slot, generation: v.generation})
					}
				case kindData:
					send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
					if len(v.body) < 4 {
						continue
					}
					payload := v.body[4:]
					if !seenAuth[v.slot] {
						seenAuth[v.slot] = true
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, body: mysqlPkt(2, []byte{0x00, 0, 0, 2, 0, 0, 0})})
						continue
					}
					if len(payload) > 0 && payload[0] == 0x01 {
						retireOnce(v.slot, v.generation)
						continue
					}
					// Model real guest readCb(): block command admission while HOLD=1.
					go func(slot uint32, gen uint64) {
						mu.Lock()
						for heldSlots[slot] {
							holdCV.Wait()
						}
						mu.Unlock()
						send(frame{kind: kindRaw, slot: slot, generation: gen, body: mysqlPkt(1, []byte{0x00, 0, 0, 2, 0, 0, 0})})
					}(v.slot, v.generation)
				case kindPeerEOF:
					retireOnce(v.slot, v.generation)
				case kindStop:
					mu.Lock()
					for s := range heldSlots {
						heldSlots[s] = false
					}
					holdCV.Broadcast()
					mu.Unlock()
					if x.Stopped != nil {
						x.Stopped(nil)
					}
					done <- nil
					return
				}
			}
			if x.Stopped != nil {
				x.Stopped(nil)
			}
			done <- nil
		}()
		return done
	}

	b, err := Start(ctx, Config{Runner: runner, Build: "fake-hold-cancel"})
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close(context.Background())

	ext, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer ext.Close()
	if err := privateHandshake(ctx, ext, "test"); err != nil {
		t.Fatalf("handshake failed: %v", err)
	}
	deadline := time.Now().Add(2 * time.Second)
	for b.Busy() && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}

	keepCtx, cancelKeep := context.WithCancel(ctx)
	keepDone := make(chan error, 1)
	go func() {
		_, err := b.SnapshotKeep(keepCtx)
		keepDone <- err
	}()

	select {
	case <-holdApplied:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for guest to apply HOLD=1")
	}
	cancelKeep()

	select {
	case err := <-keepDone:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("expected context.Canceled, got %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("SnapshotKeep did not return after cancel")
	}
	if unholdCount.Load() < 1 {
		t.Fatalf("expected HOLD=0 to be sent after cancel, got unhold=%d", unholdCount.Load())
	}

	// Next SQL on the exact same connection must complete (proves HOLD was cleared).
	if _, err := privateExec(ctx, ext, "SELECT 1"); err != nil {
		t.Fatalf("subsequent SQL on existing connection failed after canceled SnapshotKeep: %v", err)
	}
}

// P1 regression: Close sends discard mode=2, Snapshot sends capture stop without
// pre-fence SQL mutation, and shutdown_mode_failed poisons both Snapshot and Close.
func TestShutdownModePurposeAndFailurePropagation(t *testing.T) {
	t.Run("close_sends_discard_mode_2_and_propagates_failure", func(t *testing.T) {
		for _, failMode := range []bool{false, true} {
			var gotStopValue atomic.Uint64
			runner := func(x Execution) <-chan error {
				done := make(chan error, 1)
				go func() {
					source := prepared.NewRootSource(true)
					_ = x.Capture.BindRootSource(source, "fake-shutdown")
					send := func(v frame) {
						v.epoch = x.Epoch
						_ = writeFrame(x.Output, v)
					}
					send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
					for {
						v, err := readFrame(x.Input)
						if err != nil {
							break
						}
						if v.kind == kindStop {
							gotStopValue.Store(v.value)
							if failMode {
								send(frame{kind: kindPoison, body: []byte("shutdown_mode_failed")})
								send(frame{kind: kindDone, value: 0, body: []byte(`{}`)})
								if x.Stopped != nil {
									x.Stopped(errors.New("exit 21"))
								}
								done <- errors.New("exit 21")
								return
							}
							send(frame{kind: kindDone, value: 2, body: []byte(`{}`)})
							if x.Stopped != nil {
								x.Stopped(nil)
							}
							done <- nil
							return
						}
					}
					done <- nil
				}()
				return done
			}
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			b, err := Start(ctx, Config{Runner: runner, Build: "fake-shutdown"})
			if err != nil {
				t.Fatal(err)
			}
			err = b.Close(ctx)
			if gotStopValue.Load() != 2 {
				t.Fatalf("expected Close to send STOP value=2, got %d", gotStopValue.Load())
			}
			if failMode {
				if err == nil || (!strings.Contains(err.Error(), "shutdown_mode_failed") && !strings.Contains(err.Error(), "exit 21")) {
					t.Fatalf("expected shutdown_mode_failed/exit 21 error on Close, got %v", err)
				}
			} else if err != nil {
				t.Fatalf("unexpected Close error: %v", err)
			}
		}
	})

	t.Run("snapshot_rejects_without_pre_fence_open_and_fails_on_mode_error", func(t *testing.T) {
		var openCount atomic.Int32
		runner := func(x Execution) <-chan error {
			done := make(chan error, 1)
			go func() {
				source := prepared.NewRootSource(true)
				_ = x.Capture.BindRootSource(source, "fake-snap-fail")
				send := func(v frame) {
					v.epoch = x.Epoch
					_ = writeFrame(x.Output, v)
				}
				send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
				for {
					v, err := readFrame(x.Input)
					if err != nil {
						break
					}
					switch v.kind {
					case kindOpen:
						openCount.Add(1)
						send(frame{kind: kindRejected, request: v.request, value: 4, body: []byte("unexpected")})
					case kindCaptureFence:
						send(frame{kind: kindFenced, request: v.request, value: v.value, body: []byte("fenced")})
					case kindCaptureStop:
						send(frame{kind: kindStopAccepted, request: v.request, value: v.value, body: []byte("expected_owner_stop")})
						send(frame{kind: kindPoison, body: []byte("shutdown_mode_failed")})
						send(frame{kind: kindDone, value: 0, body: []byte(`{}`)})
						if x.Stopped != nil {
							x.Stopped(errors.New("exit 21"))
						}
						done <- errors.New("exit 21")
						return
					case kindStop:
						done <- nil
						return
					}
				}
				done <- nil
			}()
			return done
		}
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		b, err := Start(ctx, Config{Runner: runner, Build: "fake-snap-fail"})
		if err != nil {
			t.Fatal(err)
		}
		owned, consumed, err := b.SnapshotHeap(ctx, false)
		if openCount.Load() != 0 {
			t.Fatalf("SnapshotHeap must not open a private session before fence; got %d opens", openCount.Load())
		}
		if err == nil || (!strings.Contains(err.Error(), "shutdown_mode_failed") && !strings.Contains(err.Error(), "exit 21")) || owned != nil || !consumed {
			t.Fatalf("expected consuming shutdown_mode_failed/exit 21 error, got owned=%v consumed=%v err=%v", owned, consumed, err)
		}
	})
}

type blockingFrameWriter struct {
	io.WriteCloser
	blockKind uint8
	onBlock   func()
	mu        sync.Mutex
	blocked   bool
}

func (w *blockingFrameWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	shouldBlock := !w.blocked && len(p) >= 5 && p[4] == w.blockKind
	if shouldBlock {
		w.blocked = true
	}
	w.mu.Unlock()
	if shouldBlock && w.onBlock != nil {
		w.onBlock()
	}
	return w.WriteCloser.Write(p)
}

// P1-1 regression: canceling SnapshotKeep while writing HOLD or STATS must NOT
// close the shared guestIn pipe; existing sessions must continue executing SQL.
func TestSnapshotKeepCancelDuringControlWritePreservesExistingSession(t *testing.T) {
	for _, blockKind := range []uint8{kindHold, kindStats} {
		name := "block_hold_write"
		if blockKind == kindStats {
			name = "block_stats_write"
		}
		t.Run(name, func(t *testing.T) {
			var gotInputEOF atomic.Bool
			var unholdCount atomic.Int32
			releaseWrite := make(chan struct{})
			writeBlocked := make(chan struct{})
			var blockOnce sync.Once

			runner := func(x Execution) <-chan error {
				done := make(chan error, 1)
				go func() {
					source := prepared.NewRootSource(true)
					_ = x.Capture.BindRootSource(source, "fake-keep-write")
					send := func(v frame) {
						v.epoch = x.Epoch
						_ = writeFrame(x.Output, v)
					}
					send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
					var held atomic.Bool
					var extSlot uint32
					var extGen uint64
					var outOff uint64
					seenAuth := false
					for {
						v, err := readFrame(x.Input)
						if err != nil {
							gotInputEOF.Store(true)
							done <- err
							return
						}
						switch v.kind {
						case kindOpen:
							extSlot, extGen = v.slot, v.generation
							send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
							greet := mysqlPkt(0, []byte{0x0a, '1', '2', 0})
							send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff, body: greet})
							outOff += uint64(len(greet))
						case kindData:
							send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
							if !seenAuth {
								seenAuth = true
								ok := mysqlPkt(2, []byte{0x00, 0, 0, 2, 0, 0, 0})
								send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff, body: ok})
								outOff += uint64(len(ok))
								send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
							} else if len(v.body) >= 5 && v.body[4] == 0x03 {
								if held.Load() {
									continue
								}
								ok := mysqlPkt(1, []byte{0x00, 0, 0, 2, 0, 0, 0})
								send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff, body: ok})
								outOff += uint64(len(ok))
							}
						case kindHold:
							if v.value == 1 {
								held.Store(true)
							} else {
								held.Store(false)
								unholdCount.Add(1)
							}
							send(frame{kind: kindReply, request: v.request, slot: v.slot, generation: v.generation, body: []byte("hold_set")})
						case kindStats:
							body := fmt.Sprintf(`{"sessions":[{"slot":%d,"generation":%d,"phase":"idle","status":2}]}`, extSlot, extGen)
							send(frame{kind: kindStatsReply, request: v.request, body: []byte(body)})
						case kindStop:
							done <- nil
							return
						}
					}
				}()
				return done
			}

			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			b, err := Start(ctx, Config{Runner: runner, Build: "fake-keep-write"})
			if err != nil {
				t.Fatal(err)
			}
			defer b.Close(context.Background())

			ext, err := b.DialContext(ctx)
			if err != nil {
				t.Fatal(err)
			}
			defer ext.Close()
			if err := privateHandshake(ctx, ext, "test"); err != nil {
				t.Fatal(err)
			}
			waitPhaseIdle := time.Now().Add(2 * time.Second)
			for b.Busy() && time.Now().Before(waitPhaseIdle) {
				time.Sleep(5 * time.Millisecond)
			}

			b.writeSem <- struct{}{}
			origIn := b.in
			b.in = &blockingFrameWriter{
				WriteCloser: origIn,
				blockKind:   blockKind,
				onBlock: func() {
					blockOnce.Do(func() { close(writeBlocked) })
					<-releaseWrite
				},
			}
			<-b.writeSem

			keepCtx, cancelKeep := context.WithCancel(ctx)
			keepDone := make(chan error, 1)
			go func() {
				_, e := b.SnapshotKeep(keepCtx)
				keepDone <- e
			}()

			select {
			case <-writeBlocked:
			case <-time.After(2 * time.Second):
				t.Fatalf("timed out waiting for kind=%d write to block", blockKind)
			}
			// Cancel while writeFrame is blocked (NOT waiting for reply).
			cancelKeep()
			close(releaseWrite)

			select {
			case err := <-keepDone:
				if !errors.Is(err, context.Canceled) {
					t.Fatalf("expected context.Canceled, got %v", err)
				}
			case <-time.After(2 * time.Second):
				t.Fatal("SnapshotKeep did not return after write cancel")
			}
			if gotInputEOF.Load() || b.Failure() != nil {
				t.Fatalf("shared guestIn closed or backend failed on SnapshotKeep write cancel: eof=%v fail=%v", gotInputEOF.Load(), b.Failure())
			}
			if unholdCount.Load() < 1 {
				t.Fatalf("expected HOLD=0 cleanup after write cancel, got %d", unholdCount.Load())
			}
			if _, err := privateExec(ctx, ext, "SELECT 1"); err != nil {
				t.Fatalf("existing connection broke after SnapshotKeep write cancel: %v", err)
			}
		})
	}
}

// P1-3 regression: a stale(5) response to HOLD=1 sent before OPEN reaches the
// guest must NOT be recorded as confirmed HOLD; SnapshotKeep must retry HOLD=1
// after OPEN completes before proceeding to capture.
func TestSnapshotKeepRetriesStaleHoldBeforeOpenCompletes(t *testing.T) {
	var holdAttempts atomic.Int32
	var holdConfirmed atomic.Bool
	var keepRootWhileHeld atomic.Bool
	staleSent := make(chan struct{})
	var staleOnce sync.Once
	allowOpen := make(chan struct{})
	sentinel := errors.New("keep_root_reached_after_confirmed_hold")

	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			source := prepared.NewRootSource(true)
			_ = x.Capture.BindRootSource(source, "fake-stale-hold")
			x.Capture.SetKeep(func() (*prepared.Root, error) {
				keepRootWhileHeld.Store(holdConfirmed.Load())
				return nil, sentinel
			})
			send := func(v frame) {
				v.epoch = x.Epoch
				_ = writeFrame(x.Output, v)
			}
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
			var extSlot uint32
			var extGen uint64
			var extOpened bool
			seenAuth := map[uint32]bool{}
			outOff := map[uint32]uint64{}
			for {
				v, err := readFrame(x.Input)
				if err != nil {
					done <- nil
					return
				}
				switch v.kind {
				case kindOpen:
					if !extOpened {
						extSlot, extGen = v.slot, v.generation
						extOpened = true
					}
					send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
					greet := mysqlPkt(0, []byte{0x0a, '1', '2', 0})
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff[v.slot], body: greet})
					outOff[v.slot] += uint64(len(greet))
				case kindData:
					send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
					if !seenAuth[v.slot] {
						seenAuth[v.slot] = true
						ok := mysqlPkt(2, []byte{0x00, 0, 0, 2, 0, 0, 0})
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff[v.slot], body: ok})
						outOff[v.slot] += uint64(len(ok))
						send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
					} else if len(v.body) >= 5 && v.body[4] == 0x01 {
						send(frame{kind: kindRetired, slot: v.slot, generation: v.generation})
					} else if len(v.body) >= 5 && v.body[4] == 0x03 {
						ok := mysqlPkt(1, []byte{0x00, 0, 0, 2, 0, 0, 0})
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff[v.slot], body: ok})
						outOff[v.slot] += uint64(len(ok))
					}
				case kindHold:
					if v.value == 1 {
						holdAttempts.Add(1)
						if !extOpened {
							send(frame{kind: kindRejected, request: v.request, slot: v.slot, generation: v.generation, value: 5, body: []byte("stale")})
							staleOnce.Do(func() { close(staleSent) })
							continue
						}
						holdConfirmed.Store(true)
					}
					send(frame{kind: kindReply, request: v.request, slot: v.slot, generation: v.generation, body: []byte("hold_set")})
				case kindStats:
					if extOpened {
						body := fmt.Sprintf(`{"sessions":[{"slot":%d,"generation":%d,"phase":"idle","status":2}]}`, extSlot, extGen)
						send(frame{kind: kindStatsReply, request: v.request, body: []byte(body)})
					} else {
						send(frame{kind: kindStatsReply, request: v.request, body: []byte(`{"sessions":[]}`)})
					}
				case kindPeerEOF:
					send(frame{kind: kindRetired, slot: v.slot, generation: v.generation})
				case kindStop:
					done <- nil
					return
				}
			}
		}()
		return done
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: runner, Build: "fake-stale-hold"})
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close(context.Background())

	client, server := net.Pipe()
	defer client.Close()
	b.mu.Lock()
	s, err := b.reserveLocked(server)
	if err != nil {
		b.mu.Unlock()
		t.Fatal(err)
	}
	b.wg.Add(1)
	b.mu.Unlock()
	go func() {
		defer b.wg.Done()
		<-allowOpen
		b.attach(s)
	}()

	keepDone := make(chan error, 1)
	go func() {
		_, e := b.SnapshotKeep(ctx)
		keepDone <- e
	}()

	select {
	case <-staleSent:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for pre-OPEN stale HOLD")
	}
	close(allowOpen)
	if err := privateHandshake(ctx, client, "test"); err != nil {
		t.Fatal(err)
	}

	select {
	case err := <-keepDone:
		if !errors.Is(err, sentinel) {
			t.Fatalf("expected sentinel after confirmed HOLD, got %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("SnapshotKeep timed out")
	}
	if !keepRootWhileHeld.Load() || holdAttempts.Load() < 2 {
		t.Fatalf("expected SnapshotKeep to retry HOLD=1 after stale until confirmed; attempts=%d keptWhileHeld=%v", holdAttempts.Load(), keepRootWhileHeld.Load())
	}
}

// P1-6 regression: >16 small output frames totaling <64 KiB for a slow client
// must NOT overflow the host output queue or kill unrelated peer sessions.
func TestFragmentedOutputBelowByteLimitDoesNotFailInstance(t *testing.T) {
	const numFrames = 40
	const frameSize = 64
	burstSent := make(chan struct{})
	var burstOnce sync.Once

	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			send := func(v frame) {
				v.epoch = x.Epoch
				_ = writeFrame(x.Output, v)
			}
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
			outOff := map[uint32]uint64{}
			for {
				v, err := readFrame(x.Input)
				if err != nil {
					done <- nil
					return
				}
				switch v.kind {
				case kindOpen:
					send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
				case kindData:
					if string(v.body) == "BURST" {
						chunk := bytes.Repeat([]byte("a"), frameSize)
						for i := 0; i < numFrames; i++ {
							send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff[v.slot], body: chunk})
							outOff[v.slot] += uint64(len(chunk))
						}
						burstOnce.Do(func() { close(burstSent) })
					} else {
						resp := []byte("PONG")
						send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: outOff[v.slot], body: resp})
						outOff[v.slot] += uint64(len(resp))
					}
				case kindStop:
					done <- nil
					return
				}
			}
		}()
		return done
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: runner, Build: "fake-frag"})
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close(context.Background())

	slow, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer slow.Close()
	peer, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer peer.Close()

	if _, err := slow.Write([]byte("BURST")); err != nil {
		t.Fatal(err)
	}
	select {
	case <-burstSent:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for fragmented burst")
	}
	if _, err := peer.Write([]byte("PING")); err != nil {
		t.Fatal(err)
	}
	buf := make([]byte, 4)
	if _, err := io.ReadFull(peer, buf); err != nil || string(buf) != "PONG" {
		t.Fatalf("peer failed while slow had fragmented frames: got=%q err=%v failure=%v", buf, err, b.Failure())
	}
	if b.Failure() != nil {
		t.Fatalf("instance failed on fragmented output below 64 KiB: %v", b.Failure())
	}
	drained := make([]byte, numFrames*frameSize)
	if _, err := io.ReadFull(slow, drained); err != nil {
		t.Fatalf("slow failed to drain fragmented output: %v", err)
	}
}

// P1-7 regression: owner Close while a session writer is blocked mid-response
// must NOT send PEER_EOF(value=1) as a client disconnect before STOP(2).
func TestOwnerCloseMidResponseDoesNotSendPeerOutputEOF(t *testing.T) {
	var sawPeerOutputEOF atomic.Bool
	var gotStopValue atomic.Uint64
	writeStarted := make(chan struct{})
	var startOnce sync.Once

	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			send := func(v frame) {
				v.epoch = x.Epoch
				_ = writeFrame(x.Output, v)
			}
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
			for {
				v, err := readFrame(x.Input)
				if err != nil {
					done <- nil
					return
				}
				switch v.kind {
				case kindOpen:
					send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
				case kindData:
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: 0, body: bytes.Repeat([]byte("R"), 4096)})
					startOnce.Do(func() { close(writeStarted) })
				case kindPeerEOF:
					if v.value == 1 {
						sawPeerOutputEOF.Store(true)
						send(frame{kind: kindPoison, body: []byte("peer_output_error")})
					}
				case kindStop:
					gotStopValue.Store(v.value)
					send(frame{kind: kindDone, value: v.value, body: []byte(`{}`)})
					if x.Stopped != nil {
						x.Stopped(nil)
					}
					done <- nil
					return
				}
			}
		}()
		return done
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: runner, Build: "fake-owner-close"})
	if err != nil {
		t.Fatal(err)
	}
	c, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	if _, err := c.Write([]byte("RUN")); err != nil {
		t.Fatal(err)
	}
	select {
	case <-writeStarted:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for response chunk")
	}
	time.Sleep(30 * time.Millisecond)

	if err := b.Close(ctx); err != nil {
		t.Fatalf("owner Close mid-response failed: %v", err)
	}
	if sawPeerOutputEOF.Load() {
		t.Fatal("owner Close falsely sent PEER_EOF(value=1) to guest")
	}
	if gotStopValue.Load() != 2 {
		t.Fatalf("expected STOP(value=2), got %d", gotStopValue.Load())
	}
}

// Regression: if HOLD=0 release fails after cutting the root, SnapshotKeep must
// return an unusable error (not nil), close the created owned root, and mark
// the backend failed.
func TestSnapshotKeepHoldReleaseFailureReturnsUnusableAndClosesRoot(t *testing.T) {
	k := &keepFakeRuntime{
		statsBody:  `{"sessions":[{"slot":0,"generation":1,"phase":"idle","status":2}]}`,
		failUnhold: true,
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: k.run, Build: "fake-keep"})
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close(context.Background())

	c, err := b.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	// Drain greeting so session 0 is open and idle.
	buf := make([]byte, 64)
	if _, err := c.Read(buf); err != nil {
		t.Fatal(err)
	}

	owned, err := b.SnapshotKeep(ctx)
	if !k.rootCut.Load() {
		t.Fatal("expected SnapshotKeep to cut root before failing on HOLD=0 release")
	}
	if owned != nil {
		_ = owned.Close()
		t.Fatalf("expected nil owned root on HOLD=0 release failure, got %v", owned)
	}
	if err == nil {
		t.Fatal("expected error from SnapshotKeep when HOLD=0 release failed")
	}
	var rej *Rejected
	if !errors.As(err, &rej) || rej.Code != "unusable" {
		t.Fatalf("expected unusable Rejected error, got %v", err)
	}
	if b.Failure() == nil {
		t.Fatal("expected backend Failure() to be recorded after HOLD=0 release failure")
	}
	if b.CaptureDebt() != nil {
		t.Fatalf("unexpected capture debt after closing created root: %v", b.CaptureDebt())
	}
}

type blockingWriteConn struct {
	net.Conn
	writeEntered  chan struct{}
	releaseWriter chan struct{}
	enterOnce     sync.Once
}

func (c *blockingWriteConn) Write(p []byte) (int, error) {
	c.enterOnce.Do(func() { close(c.writeEntered) })
	<-c.releaseWriter
	return c.Conn.Write(p)
}

type singleConnListener struct {
	ch     chan net.Conn
	closed chan struct{}
	once   sync.Once
}

func newSingleConnListener(c net.Conn) *singleConnListener {
	ch := make(chan net.Conn, 1)
	ch <- c
	return &singleConnListener{ch: ch, closed: make(chan struct{})}
}

func (l *singleConnListener) Accept() (net.Conn, error) {
	select {
	case c := <-l.ch:
		return c, nil
	case <-l.closed:
		return nil, net.ErrClosed
	}
}
func (l *singleConnListener) Close() error {
	l.once.Do(func() { close(l.closed) })
	return nil
}
func (l *singleConnListener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 1}
}

// Regression: CloseWithStopped must not notify success while a host relay writer
// is still active even after the guest stops, and once relays finish it must
// notify without waiting for background memory reclamation (complete channel).
func TestCloseWithStoppedWaitsForRelaysNotMemoryRelease(t *testing.T) {
	guestStopped := make(chan struct{})
	releaseMemory := make(chan struct{})
	writeEntered := make(chan struct{})
	releaseWriter := make(chan struct{})

	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			send := func(v frame) {
				v.epoch = x.Epoch
				_ = writeFrame(x.Output, v)
			}
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
			var openSlot uint32
			var openGen uint64
			for {
				v, err := readFrame(x.Input)
				if err != nil {
					break
				}
				switch v.kind {
				case kindOpen:
					openSlot, openGen = v.slot, v.generation
					send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: 0, body: []byte("HELLO")})
				case kindStop:
					if openGen != 0 {
						send(frame{kind: kindRetired, slot: openSlot, generation: openGen})
					}
					send(frame{kind: kindDone, value: v.value, body: []byte(`{}`)})
					if x.Stopped != nil {
						x.Stopped(nil)
					}
					close(guestStopped)
					<-releaseMemory
					done <- nil
					return
				}
			}
			if x.Stopped != nil {
				x.Stopped(nil)
			}
			done <- nil
		}()
		return done
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	b, err := Start(ctx, Config{Runner: runner, Build: "fake-close-async"})
	if err != nil {
		t.Fatal(err)
	}

	clientSide, serverRaw := net.Pipe()
	defer clientSide.Close()
	heldConn := &blockingWriteConn{Conn: serverRaw, writeEntered: writeEntered, releaseWriter: releaseWriter}
	ln := newSingleConnListener(heldConn)
	if err := b.Serve(ln); err != nil {
		t.Fatal(err)
	}

	select {
	case <-writeEntered:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for relay writer to enter Write")
	}

	stopped := make(chan error, 1)
	closeDone := make(chan error, 1)
	go func() {
		closeDone <- b.CloseWithStopped(ctx, func(e error) { stopped <- e })
	}()

	select {
	case <-guestStopped:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for guest to stop")
	}

	// While relay writer is still held, stop notification must NOT fire.
	select {
	case e := <-stopped:
		t.Fatalf("CloseWithStopped notified early while writer was still active (active=%d, err=%v)", b.Active(), e)
	case <-time.After(50 * time.Millisecond):
	}
	if active := b.Active(); active != 1 {
		t.Fatalf("expected active=1 while writer is held, got %d", active)
	}

	// Release writer while memory reclamation is STILL blocked: notification must fire now.
	close(releaseWriter)
	select {
	case e := <-stopped:
		if e != nil {
			t.Fatalf("expected nil stop notification after relays stopped, got %v", e)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("CloseWithStopped did not notify after relays stopped while memory release remained gated")
	}
	if active := b.Active(); active != 0 {
		t.Fatalf("expected active=0 after stop notification, got %d", active)
	}
	if b.DisposalComplete() {
		t.Fatal("expected DisposalComplete() == false while memory release is still gated")
	}

	// Now unblock memory reclamation and confirm full disposal completes cleanly.
	close(releaseMemory)
	select {
	case e := <-closeDone:
		if e != nil {
			t.Fatalf("CloseWithStopped returned error: %v", e)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("CloseWithStopped did not finish after memory release")
	}
	if !b.DisposalComplete() {
		t.Fatal("expected DisposalComplete() == true after memory release")
	}
}
