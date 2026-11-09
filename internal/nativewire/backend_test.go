package nativewire

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// This peer speaks only the private envelope. It is deliberately not an engine,
// MySQL decoder or runtime substitute: native/public acceptance remains C2/C3.
type fakeRuntime struct {
	execution    chan Execution
	opens        chan frame
	payload      chan []byte
	fail         chan error
	release      <-chan struct{}
	noReady      bool
	noOpen       bool
	rejection    uint64
	fences       atomic.Int32
	finishPoison <-chan struct{}
}

func newFake() *fakeRuntime {
	return &fakeRuntime{execution: make(chan Execution, 1), opens: make(chan frame, 64), payload: make(chan []byte, 64), fail: make(chan error, 1)}
}
func (f *fakeRuntime) run(x Execution) <-chan error {
	f.execution <- x
	done := make(chan error, 1)
	go func() {
		var failure error
		frames := make(chan frame)
		abortReader := make(chan struct{})
		inputDone := make(chan struct{})
		go func() {
			defer close(inputDone)
			defer close(frames)
			for {
				v, e := readFrame(x.Input)
				if e != nil {
					return
				}
				select {
				case frames <- v:
				case <-abortReader:
					return
				}
			}
		}()
		send := func(v frame) {
			v.epoch = x.Epoch
			if e := writeFrame(x.Output, v); e != nil {
				failure = e
			}
		}
		source := prepared.NewRootSource(true)
		if e := x.Capture.BindRootSource(source, "fake-guest"); e != nil {
			failure = e
		}
		if !f.noReady {
			send(frame{kind: kindReady, body: []byte(`{"lifecycle_profile":3}`)})
		}
	loop:
		for {
			select {
			case <-f.finishPoison:
				send(frame{kind: kindPoison, body: []byte("deadline")})
				break loop
			case e := <-f.fail:
				x.Failure(e)
				failure = e
			case v, ok := <-frames:
				if !ok {
					break loop
				}
				switch v.kind {
				case kindOpen:
					f.opens <- v
					if !f.noOpen {
						send(frame{kind: kindOpened, request: v.request, slot: v.slot, generation: v.generation})
						send(frame{kind: kindState, slot: v.slot, generation: v.generation, body: []byte("idle")})
					}
				case kindData:
					f.payload <- v.body
					send(frame{kind: kindCredit, slot: v.slot, generation: v.generation, value: v.value + uint64(len(v.body))})
					send(frame{kind: kindRaw, slot: v.slot, generation: v.generation, value: v.value, body: v.body})
				case 7:
					send(frame{kind: 108, request: v.request})
				case kindPeerEOF:
					send(frame{kind: kindRetired, slot: v.slot, generation: v.generation})
				case kindStop:
					break loop
				case kindCaptureFence:
					f.fences.Add(1)
					k := byte(kindFenced)
					value := v.value
					if f.rejection != 0 {
						k = kindRejected
						value = f.rejection
					}
					send(frame{kind: k, request: v.request, value: value, body: []byte("test precondition")})
				case kindCaptureStop:
					send(frame{kind: kindStopAccepted, request: v.request, value: v.value})
					send(frame{kind: kindCaptureStopped, request: v.request, value: v.value})
					if e := <-x.Approval; e != nil {
						failure = e
					} else {
						failure = x.Capture.CompleteRoot(source, "fake-guest", []string{"."}, nil)
					}
					break loop
				}
			}
		}
		// Drain any host STOP after capture/ordinary stop so the writer can join.
		// The execution contract is send-after-all-access, including this peer reader.
		close(abortReader)
		if closer, ok := x.Input.(io.Closer); ok {
			_ = closer.Close()
		}
		<-inputDone
		if f.release != nil {
			<-f.release
		}
		done <- failure
	}()
	return done
}
func startFake(t *testing.T, f *fakeRuntime) (*Backend, Execution) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	b, e := Start(ctx, Config{Runner: f.run, Build: "fake-guest", QueryTimeout: 123456789})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = b.Close(ctx)
	})
	return b, <-f.execution
}
func waitFor(t *testing.T, ch <-chan struct{}) {
	t.Helper()
	select {
	case <-ch:
	case <-time.After(3 * time.Second):
		t.Fatal("join/notification did not arrive")
	}
}
func remainsOpen(t *testing.T, ch <-chan struct{}) {
	t.Helper()
	select {
	case <-ch:
		t.Fatal("completed before held owner joined")
	default:
	}
}
func nextOpen(t *testing.T, f *fakeRuntime) frame {
	t.Helper()
	select {
	case v := <-f.opens:
		return v
	case <-time.After(3 * time.Second):
		t.Fatal("missing OPEN")
		return frame{}
	}
}
func waitActive(t *testing.T, b *Backend, n int) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for b.Active() != n {
		if time.Now().After(deadline) {
			t.Fatalf("Active=%d want %d", b.Active(), n)
		}
		time.Sleep(time.Millisecond)
	}
}

func TestBackendOpaqueRelayAndTypedTimeout(t *testing.T) {
	f := newFake()
	b, _ := startFake(t, f)
	c, e := b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	v := nextOpen(t, f)
	if v.value != 123456789 || v.epoch != b.epoch || v.generation == 0 {
		t.Fatalf("OPEN=%+v", v)
	}
	// Not valid MySQL: relaying it unchanged proves no packet parser is required.
	payload := []byte{255, 0, 42, 0, 17, 250}
	errc := make(chan error, 1)
	go func() { _, e := c.Write(payload); errc <- e }()
	out := make([]byte, len(payload))
	if _, e = io.ReadFull(c, out); e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(out, payload) {
		t.Fatalf("opaque output %v", out)
	}
	if e = <-errc; e != nil {
		t.Fatal(e)
	}
	_ = c.Close()
	waitActive(t, b, 0)
	if e = b.Failure(); e != nil {
		t.Fatal(e)
	}
}

// A listener without sockets keeps the unit suite portable. Real TCP/public
// routing and bounded1040 serialization are explicitly later acceptance work.
type channelListener struct {
	accept chan net.Conn
	done   chan struct{}
	once   sync.Once
}

func newListener() *channelListener {
	return &channelListener{make(chan net.Conn), make(chan struct{}), sync.Once{}}
}
func (l *channelListener) Accept() (net.Conn, error) {
	select {
	case c := <-l.accept:
		return c, nil
	case <-l.done:
		return nil, net.ErrClosed
	}
}
func (l *channelListener) Close() error { l.once.Do(func() { close(l.done) }); return nil }
func (l *channelListener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 9999}
}
func TestBackendSharedAdmissionAndCanceledDial(t *testing.T) {
	f := newFake()
	b, _ := startFake(t, f)
	var rejected atomic.Int32
	b.rejectCapacity = func(c net.Conn) { rejected.Add(1); _ = c.Close() }
	l := newListener()
	if e := b.Serve(l); e != nil {
		t.Fatal(e)
	}
	if b.Port() != 9999 {
		t.Fatal(b.Port())
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if c, e := b.DialContext(ctx); c != nil || !errors.Is(e, context.Canceled) {
		t.Fatalf("canceled dial %v %v", c, e)
	}
	var clients []net.Conn
	for i := 0; i < Capacity; i++ {
		var c net.Conn
		if i%2 == 0 {
			var e error
			c, e = b.DialContext(context.Background())
			if e != nil {
				t.Fatal(e)
			}
		} else {
			var server net.Conn
			c, server = net.Pipe()
			l.accept <- server
		}
		clients = append(clients, c)
		nextOpen(t, f)
	}
	defer func() {
		for _, c := range clients {
			_ = c.Close()
		}
	}()
	if c, e := b.DialContext(context.Background()); c != nil || !errors.Is(e, ErrCapacity) {
		t.Fatalf("capacity dial %v %v", c, e)
	}
	c, s := net.Pipe()
	l.accept <- s
	_ = c.SetReadDeadline(time.Now().Add(3 * time.Second))
	var one [1]byte
	if _, e := c.Read(one[:]); !errors.Is(e, io.EOF) {
		t.Fatalf("rejection did not close: %v", e)
	}
	_ = c.Close()
	if rejected.Load() != 1 || b.Active() != Capacity {
		t.Fatalf("reject=%d active=%d", rejected.Load(), b.Active())
	}
	select {
	case v := <-f.opens:
		t.Fatalf("rejected admission started OPEN %+v", v)
	default:
	}
}
func TestBackendFailureImmediateDoneWaitsForExecution(t *testing.T) {
	release := make(chan struct{})
	f := newFake()
	f.release = release
	f.noOpen = true
	b, _ := startFake(t, f)
	c, e := b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	nextOpen(t, f)
	cause := fmt.Errorf("held worker: %w", context.DeadlineExceeded)
	f.fail <- cause
	waitFor(t, b.failed)
	if !errors.Is(b.Failure(), context.DeadlineExceeded) {
		t.Fatal(b.Failure())
	}
	_ = c.SetReadDeadline(time.Now().Add(time.Second))
	var one [1]byte
	if _, e := c.Read(one[:]); !errors.Is(e, io.EOF) {
		t.Fatalf("fatal stream: %v", e)
	}
	remainsOpen(t, b.Done())
	if b.DisposalComplete() || b.Active() != 1 {
		t.Fatalf("early release: active=%d disposed=%v", b.Active(), b.DisposalComplete())
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := b.Close(ctx)
	if !errors.Is(err, cause) || len(disposal.Owners(err)) != 1 {
		t.Fatalf("lost cause or owner: %v", err)
	}
	close(release)
	waitFor(t, b.Done())
	if e = disposal.Retry(context.Background(), err); e != nil {
		t.Fatal(e)
	}
	if !b.DisposalComplete() || b.Active() != 0 || !errors.Is(b.Failure(), cause) {
		t.Fatalf("late cleanup changed cause: %v", b.Failure())
	}
}
func TestBackendCanceledStartupOwnsLateParentRemoval(t *testing.T) {
	f := newFake()
	f.noReady = true
	release := make(chan struct{})
	f.release = release
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() { _, e := Start(ctx, Config{Runner: f.run, Build: "fake-guest"}); result <- e }()
	<-f.execution
	cancel()
	err := <-result
	if !errors.Is(err, context.Canceled) || len(disposal.Owners(err)) != 1 {
		t.Fatalf("startup: %v", err)
	}
	parent := filepath.Join(t.TempDir(), "parent")
	if e := os.Mkdir(parent, 0700); e != nil {
		t.Fatal(e)
	}
	err = disposal.RemoveAfter(err, parent)
	if _, e := os.Stat(parent); e != nil {
		t.Fatalf("parent removed before execution join: %v", e)
	}
	close(release)
	if e := disposal.Retry(context.Background(), err); e != nil {
		t.Fatal(e)
	}
	if _, e := os.Stat(parent); !os.IsNotExist(e) {
		t.Fatalf("late parent remains: %v", e)
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatal("cleanup forgave original cancellation")
	}
}
func TestBackendCaptureFenceRejectionAndOwnership(t *testing.T) {
	for _, rejection := range []uint64{0, 1, 2} {
		t.Run(fmt.Sprint(rejection), func(t *testing.T) {
			f := newFake()
			f.rejection = rejection
			b, _ := startFake(t, f)
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			owned, consumed, e := b.SnapshotHeap(ctx, false)
			if f.fences.Load() != 1 {
				t.Fatal("cached idle bypassed guest fence")
			}
			if rejection != 0 {
				var rejected *Rejected
				if owned != nil || consumed || !errors.As(e, &rejected) {
					t.Fatalf("rejected capture: %v %v %v", owned, consumed, e)
				}
				want := "busy"
				if rejection == 2 {
					want = "transaction_active"
				}
				if rejected.Code != want {
					t.Fatal(rejected.Code)
				}
				c, e := b.DialContext(ctx)
				if e != nil {
					t.Fatal("source consumed", e)
				}
				_ = c.Close()
			} else {
				if owned == nil || !consumed || e != nil {
					t.Fatalf("capture: %v %v %v", owned, consumed, e)
				}
				if !b.DisposalComplete() {
					t.Fatal("successful capture left physical cleanup")
				}
				if e := owned.Close(); e != nil {
					t.Fatal(e)
				}
			}
		})
	}
}

type heldWriteConn struct {
	net.Conn
	entered chan struct{}
	release <-chan struct{}
	once    sync.Once
}

func (c *heldWriteConn) Write(p []byte) (int, error) {
	c.once.Do(func() { close(c.entered) })
	<-c.release
	return c.Conn.Write(p)
}
func releaseEventually(ch chan struct{}) {
	select {
	case <-ch:
	default:
		close(ch)
	}
}
func TestBackendDoneWaitsForHostRelayAfterExecution(t *testing.T) {
	f := newFake()
	b, _ := startFake(t, f)
	l := newListener()
	if e := b.Serve(l); e != nil {
		t.Fatal(e)
	}
	c, server := net.Pipe()
	defer c.Close()
	release := make(chan struct{})
	defer releaseEventually(release)
	held := &heldWriteConn{Conn: server, entered: make(chan struct{}), release: release}
	l.accept <- held
	nextOpen(t, f)
	if _, e := c.Write([]byte("opaque")); e != nil {
		t.Fatal(e)
	}
	waitFor(t, held.entered)
	cause := errors.New("native worker failed while host write held")
	f.fail <- cause
	waitFor(t, b.executionDone)
	remainsOpen(t, b.Done())
	if b.Active() != 1 || b.DisposalComplete() {
		t.Fatal("host relay released early")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := b.Close(ctx)
	if !errors.Is(err, cause) || len(disposal.Owners(err)) != 1 {
		t.Fatalf("lost held relay owner: %v", err)
	}
	releaseEventually(release)
	waitFor(t, b.Done())
	if e := disposal.Retry(context.Background(), err); e != nil {
		t.Fatal(e)
	}
}
func TestBackendPendingOpenCaptureAndFirstCause(t *testing.T) {
	f := newFake()
	f.noOpen = true
	b, _ := startFake(t, f)
	c, e := b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	nextOpen(t, f)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	o, consumed, e := b.SnapshotHeap(ctx, false)
	if o != nil || consumed || !errors.Is(e, ErrBusy) || f.fences.Load() != 0 {
		t.Fatalf("pending OPEN capture %v %v %v", o, consumed, e)
	}
	if !b.Busy() {
		t.Fatal("unknown session state reported idle")
	}
	b.receiveFrame(frame{kind: kindPoison, epoch: b.epoch, body: []byte("deadline")})
	if !errors.Is(b.Failure(), context.DeadlineExceeded) {
		t.Fatal(b.Failure())
	}
	b.fail(errors.New("later EOF must not overwrite deadline"))
	if !errors.Is(b.Failure(), context.DeadlineExceeded) {
		t.Fatal("first cause overwritten")
	}
	// The pending OPEN RPC must wake from failure, not its fixed8s deadline.
	waitFor(t, b.Done())
}
func TestBackendStaleStateCannotChangeCurrentSession(t *testing.T) {
	f := newFake()
	b, _ := startFake(t, f)
	c, e := b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	first := nextOpen(t, f)
	_ = c.Close()
	waitActive(t, b, 0)
	c, e = b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	current := nextOpen(t, f)
	if _, e := b.rpc(frame{kind: 7}); e != nil {
		t.Fatal(e)
	}
	// Inject through the same control receive boundary; no MySQL bytes examined.
	b.receiveFrame(frame{kind: kindState, epoch: b.epoch, slot: current.slot, generation: current.generation, body: []byte("executing")})
	b.receiveFrame(frame{kind: kindState, epoch: b.epoch, slot: first.slot, generation: first.generation, body: []byte("idle")})
	b.mu.Lock()
	phase := b.sessions[key{current.slot, current.generation}].phase
	b.mu.Unlock()
	if phase != "executing" {
		t.Fatalf("stale state overwrote current: %s", phase)
	}
}
func TestBackendRejectsInvalidConfigurationBeforeRunner(t *testing.T) {
	var called atomic.Int32
	runner := func(Execution) <-chan error { called.Add(1); return nil }
	for _, cfg := range []Config{{Runner: runner, Build: "fake-guest", QueryTimeout: -1}, {Runner: runner}, {Build: "fake-guest"}} {
		if b, e := Start(context.Background(), cfg); b != nil || e == nil {
			t.Fatalf("invalid config %v %v", b, e)
		}
	}
	if called.Load() != 0 {
		t.Fatal("invalid configuration started execution")
	}
}

func TestBackendNativeCauseSurvivesRuntimeCompletion(t *testing.T) {
	trigger := make(chan struct{})
	f := newFake()
	f.finishPoison = trigger
	b, _ := startFake(t, f)
	close(trigger)
	waitFor(t, b.Done())
	if !errors.Is(b.Failure(), context.DeadlineExceeded) {
		t.Fatalf("native cause replaced by completion: %v", b.Failure())
	}
}

func TestBackendStartupPreservesCompletedRuntimeCause(t *testing.T) {
	cause := errors.New("original bootstrap worker failure")
	for i := 0; i < 100; i++ {
		runner := func(Execution) <-chan error { done := make(chan error, 1); done <- cause; return done }
		b, e := Start(context.Background(), Config{Runner: runner, Build: "fake-guest"})
		if b != nil || !errors.Is(e, cause) {
			t.Fatalf("original startup cause lost: %v %v", b, e)
		}
		if err := disposal.Retry(context.Background(), e); err != nil {
			t.Fatal(err)
		}
	}
}
