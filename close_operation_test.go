package mariamem

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/nativewire"
	"github.com/masahitojp/mariamem/internal/prepared"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"
)

// A stopped backend can keep reclaiming resources after its notification.
// The actual guest/transport producer of this boundary belongs to #205.
type stagedCloseBackend struct {
	fakeBackend
	started  chan struct{}
	stopped  chan struct{}
	release  chan struct{}
	calls    atomic.Int32
	disposed atomic.Bool
	fail     atomic.Bool
	result   error
}

func newStagedClose() *stagedCloseBackend {
	return &stagedCloseBackend{started: make(chan struct{}), stopped: make(chan struct{}), release: make(chan struct{})}
}
func (b *stagedCloseBackend) Failure() error {
	if b.fail.Load() {
		return errors.New("injected crash")
	}
	return nil
}
func (b *stagedCloseBackend) DisposalComplete() bool { return b.disposed.Load() }
func (b *stagedCloseBackend) Close(ctx context.Context) error {
	if b.disposed.Load() {
		return b.result
	}
	return b.CloseWithStopped(ctx, func(error) {})
}
func (b *stagedCloseBackend) CloseWithStopped(ctx context.Context, notify func(error)) error {
	if b.calls.Add(1) != 1 {
		panic("duplicate initial shutdown")
	}
	close(b.started)
	<-b.stopped
	notify(nil)
	<-b.release
	b.disposed.Store(true)
	return b.result
}
func closeTestDB(b *stagedCloseBackend) *Database {
	return &Database{server: b, opts: Options{ShutdownTimeout: time.Second}}
}
func closeTestContext(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	t.Cleanup(cancel)
	return ctx
}

func TestCloseOperationSharedAndCancellation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	stopped := make(chan *closeOperation, 1)
	go func() {
		op, err := db.stopForCleanup(ctx)
		if err != nil {
			t.Error(err)
		}
		stopped <- op
	}()
	<-b.started
	if !db.Closed() {
		t.Fatal("still accepting work")
	}
	if _, err := db.DialContext(ctx, "tcp", "ignored"); !errors.Is(err, ErrClosed) {
		t.Fatal("new request accepted", err)
	}
	result := errors.New("saved cleanup result")
	b.result = result
	close(b.stopped)
	op := <-stopped
	if op.Disposed() {
		t.Fatal("disposed before cleanup")
	}
	canceled, cancel := context.WithCancel(ctx)
	cancel()
	if err := op.Wait(canceled); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	results := make(chan error, 12)
	for i := 0; i < 12; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); results <- db.Close() }()
	}
	select {
	case err := <-results:
		t.Fatal("Close returned before result", err)
	default:
	}
	// Normal completion must not be classified as a watch-detected crash.
	done := make(chan struct{})
	close(done)
	db.watch(done)
	if db.Err() != nil {
		t.Fatal("intentional shutdown marked failed", db.Err())
	}
	close(b.release)
	wg.Wait()
	for i := 0; i < 12; i++ {
		if err := <-results; !errors.Is(err, result) {
			t.Fatal(err)
		}
	}
	if err := op.Wait(ctx); !errors.Is(err, result) {
		t.Fatal(err)
	}
	if !op.Disposed() {
		t.Fatal("missing disposal confirmation")
	}
	if !errors.Is(db.Close(), result) || b.calls.Load() != 1 {
		t.Fatal("changed saved result")
	}
}

func TestWatchStartsSameCloseOperation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	b.fail.Store(true)
	done := make(chan struct{})
	close(done)
	watchDone := make(chan struct{})
	go func() { db.watch(done); close(watchDone) }()
	<-b.started
	if !errors.Is(db.Err(), ErrUnusable) {
		t.Fatal("lost crash", db.Err())
	}
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	db.mu.Lock()
	same := db.closing == op
	db.mu.Unlock()
	if !same {
		t.Fatal("different owner")
	}
	close(b.release)
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	<-watchDone
	if !errors.Is(db.Err(), ErrUnusable) || b.calls.Load() != 1 {
		t.Fatal("lost cause or duplicate shutdown")
	}
}

func TestPendingCloseHoldsCapacityWithoutBlockingPool(t *testing.T) {
	for _, cap := range []int{1, 2} {
		t.Run(string(rune('0'+cap)), func(t *testing.T) {
			b := newStagedClose()
			db := closeTestDB(b)
			ctx := closeTestContext(t)
			pool, _ := forklimit.New(cap)
			lease, _ := pool.Acquire(ctx)
			if err := lease.Activate(); err != nil {
				t.Fatal(err)
			}
			db.lease = lease
			close(b.stopped)
			op, err := db.stopForCleanup(ctx)
			if err != nil {
				t.Fatal(err)
			}
			if _, occupied := pool.Usage(); occupied != 1 {
				t.Fatal("premature lease release")
			}
			next, err := pool.TryAcquire(false)
			if cap == 1 && !errors.Is(err, forklimit.ErrFull) {
				t.Fatal("expected occupied capacity", err)
			}
			if cap == 2 {
				if err != nil {
					t.Fatal("normal pending blocked whole pool", err)
				}
				next.Cancel()
			}
			close(b.release)
			if err := op.Wait(ctx); err != nil {
				t.Fatal(err)
			}
			next, err = pool.Acquire(ctx)
			if err != nil {
				t.Fatal(err)
			}
			next.Cancel()
		})
	}
}

func TestLiveJoinsInitialCloseBeforeRetry(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	result := make(chan error, 1)
	go func() { result <- (liveChild{db}).Close() }()
	select {
	case err := <-result:
		t.Fatal("Live did not join", err)
	default:
	}
	close(b.release)
	if err := <-result; err != nil {
		t.Fatal(err)
	}
	if err := op.Wait(ctx); err != nil {
		t.Fatal(err)
	}
	if b.calls.Load() != 1 {
		t.Fatal("duplicate shutdown")
	}
}

func TestStopWaitCancellationKeepsSharedOperation(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	waiting, cancel := context.WithCancel(ctx)
	result := make(chan *closeOperation, 1)
	go func() {
		op, err := db.stopForCleanup(waiting)
		if !errors.Is(err, context.Canceled) {
			t.Error(err)
		}
		result <- op
	}()
	<-b.started
	cancel()
	first := <-result
	if first == nil {
		t.Fatal("lost cleanup handle")
	}
	close(b.stopped)
	second, err := db.stopForCleanup(ctx)
	if err != nil || first != second {
		t.Fatal("lost shared operation", err)
	}
	close(b.release)
	if err := second.Wait(ctx); err != nil {
		t.Fatal(err)
	}
}

func TestSnapshotCloseDuringChildCleanup(t *testing.T) {
	s := controlledSnapshot(t, 1)
	ctx := closeTestContext(t)
	lease, err := s.forkLimit().TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	b := newStagedClose()
	db := closeTestDB(b)
	db.lease = lease
	close(b.stopped)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	wait := &capacityWaitContext{Context: ctx, waiting: make(chan struct{})}
	next := make(chan error, 1)
	go func() { _, err := s.Fork(wait); next <- err }()
	select {
	case <-wait.waiting:
	case <-ctx.Done():
		t.Fatal("Fork did not wait", ctx.Err())
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case err := <-next:
		if !errors.Is(err, ErrClosed) {
			t.Fatal(err)
		}
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if op.Disposed() {
		t.Fatal("parent Close claimed child disposal")
	}
	if _, occupied := s.forkLimit().Usage(); occupied != 1 {
		t.Fatal("parent released active child")
	}
	close(b.release)
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	if _, occupied := s.forkLimit().Usage(); occupied != 0 {
		t.Fatal("child lease retained after confirmed disposal")
	}
}

func TestCloseResultSurvivesLateDisposal(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	var allow atomic.Bool
	failure := errors.New("cleanup failed")
	owner := disposal.New(func(context.Context) error {
		if !allow.Load() {
			return failure
		}
		return nil
	})
	b.result = disposal.Retain(nil, failure, owner)
	close(b.stopped)
	close(b.release)
	op, err := db.stopForCleanup(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if err := op.Wait(ctx); !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if op.Disposed() {
		t.Fatal("failed cleanup reported disposed")
	}
	allow.Store(true)
	if err := disposal.Retry(ctx, b.result); err != nil {
		t.Fatal(err)
	}
	if !op.Disposed() {
		t.Fatal("late successful release not observable")
	}
	if !errors.Is(db.Close(), failure) {
		t.Fatal("late release rewrote saved result")
	}
}

// Keep the real producer from silently falling back to synchronous-only Close.
var _ interface {
	CloseWithStopped(context.Context, func(error)) error
} = (*host.Native)(nil)

func TestPublicCloseAsyncHandle(t *testing.T) {
	b := newStagedClose()
	db := closeTestDB(b)
	ctx := closeTestContext(t)
	canceled, cancel := context.WithCancel(ctx)
	cancel()
	if h, e := db.CloseAsync(canceled); h != nil || !errors.Is(e, context.Canceled) {
		t.Fatal(h, e)
	}
	if db.closed {
		t.Fatal("canceled request initiated shutdown")
	}
	close(b.stopped)
	h, e := db.CloseAsync(ctx)
	if e != nil || h == nil || !db.Closed() {
		t.Fatal(h, e)
	}
	if h.Disposed() {
		t.Fatal("cleanup still gated")
	}
	if e = h.Wait(canceled); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
	close(b.release)
	if e = h.Wait(ctx); e != nil || !h.Disposed() {
		t.Fatal(e)
	}
	if e = db.Close(); e != nil {
		t.Fatal(e)
	}
	if b.calls.Load() != 1 {
		t.Fatal("duplicate shutdown")
	}
}

func TestPublicCloseAsyncRetainsConsumedCaptureDebt(t *testing.T) {
	for _, withLease := range []bool{false, true} {
		t.Run(map[bool]string{false: "root", true: "fork"}[withLease], func(t *testing.T) {
			ctx := closeTestContext(t)
			b := newStagedClose()
			b.disposed.Store(true)
			db := closeTestDB(b)
			var pool *forklimit.Pool
			if withLease {
				var e error
				pool, e = forklimit.New(1)
				if e != nil {
					t.Fatal(e)
				}
				db.lease, e = pool.Acquire(ctx)
				if e != nil {
					t.Fatal(e)
				}
				if e = db.lease.Activate(); e != nil {
					t.Fatal(e)
				}
				defer db.lease.Settle(nil)
			}
			backing, fd := physicalBacking(t)
			captureErr := errors.New("capture failed after consuming source")
			b.snapshot = func(context.Context, bool) (*stored.Owned, bool, error) {
				if e := syscall.Close(fd); e != nil {
					t.Fatal(e)
				}
				return backing, true, captureErr
			}
			_, e := db.Snapshot(ctx, SnapshotOptions{})
			if !errors.Is(e, captureErr) || !errors.Is(e, syscall.EBADF) {
				t.Fatal(e)
			}
			if !errors.Is(db.captureDebt, syscall.EBADF) {
				t.Fatal("capture debt lost", db.captureDebt)
			}
			h, stopErr := db.CloseAsync(ctx)
			if h == nil || !errors.Is(stopErr, syscall.EBADF) {
				t.Fatal("cleanup failure missing from stop result", h, stopErr)
			}
			first := h.Wait(ctx)
			if !errors.Is(first, syscall.EBADF) || h.Disposed() {
				t.Fatal("false successful disposal", first)
			}
			if db.Close() != first {
				t.Fatal("Close did not share stable cleanup result")
			}
			if b.calls.Load() != 0 {
				t.Fatal("consumed source shut down twice")
			}
			if pool != nil {
				if _, occupied := pool.Usage(); occupied != 1 {
					t.Fatal("unresolved capture returned Fork slot")
				}
			}
		})
	}
}

func testNativeWireFrameWrite(w io.Writer, kind byte, req, slot uint32, epoch, gen, val uint64, body []byte) error {
	var hdr [37]byte
	binary.LittleEndian.PutUint32(hdr[0:4], uint32(33+len(body)))
	hdr[4] = kind
	binary.LittleEndian.PutUint32(hdr[5:9], req)
	binary.LittleEndian.PutUint32(hdr[9:13], slot)
	binary.LittleEndian.PutUint64(hdr[13:21], epoch)
	binary.LittleEndian.PutUint64(hdr[21:29], gen)
	binary.LittleEndian.PutUint64(hdr[29:37], val)
	if _, err := w.Write(hdr[:]); err != nil {
		return err
	}
	if len(body) > 0 {
		_, err := w.Write(body)
		return err
	}
	return nil
}

func testNativeWireFrameRead(r io.Reader) (kind byte, req, slot uint32, epoch, gen, val uint64, body []byte, err error) {
	var lb [4]byte
	if _, err = io.ReadFull(r, lb[:]); err != nil {
		return
	}
	n := binary.LittleEndian.Uint32(lb[:])
	buf := make([]byte, n)
	if _, err = io.ReadFull(r, buf); err != nil {
		return
	}
	kind = buf[0]
	req = binary.LittleEndian.Uint32(buf[1:5])
	slot = binary.LittleEndian.Uint32(buf[5:9])
	epoch = binary.LittleEndian.Uint64(buf[9:17])
	gen = binary.LittleEndian.Uint64(buf[17:25])
	val = binary.LittleEndian.Uint64(buf[25:33])
	body = buf[33:]
	return
}

func testMySQLPkt(seq byte, payload []byte) []byte {
	out := make([]byte, 4+len(payload))
	out[0], out[1], out[2], out[3] = byte(len(payload)), byte(len(payload)>>8), byte(len(payload)>>16), seq
	copy(out[4:], payload)
	return out
}

func TestPublicSnapshotKeepHoldReleaseFailureReturnsErrUnusable(t *testing.T) {
	ctx := closeTestContext(t)
	var rootCut atomic.Bool
	runner := func(x nativewire.Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			source := prepared.NewRootSource(true)
			_ = x.Capture.BindRootSource(source, "pub-keep-unusable")
			x.Capture.SetKeep(func() (*prepared.Root, error) {
				rootCut.Store(true)
				var c prepared.Capture
				if err := c.BindRootSource(source, "pub-keep-unusable"); err != nil {
					return nil, err
				}
				c.Request()
				if err := c.CompleteRoot(source, "pub-keep-unusable", []string{"."}, nil); err != nil {
					return nil, err
				}
				return c.TakeRoot("pub-keep-unusable")
			})
			_ = testNativeWireFrameWrite(x.Output, 100, 0, 0, x.Epoch, 0, 0, []byte(`{"lifecycle_profile":3}`))
			seenAuth := map[uint32]bool{}
			for {
				kind, req, slot, _, gen, val, body, err := testNativeWireFrameRead(x.Input)
				if err != nil {
					break
				}
				switch kind {
				case 1: // OPEN
					_ = testNativeWireFrameWrite(x.Output, 101, req, slot, x.Epoch, gen, 0, nil)
					_ = testNativeWireFrameWrite(x.Output, 107, 0, slot, x.Epoch, gen, 0, []byte("idle"))
					_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, testMySQLPkt(0, []byte{0x0a, '1', '2', 0}))
				case 2: // DATA
					_ = testNativeWireFrameWrite(x.Output, 106, 0, slot, x.Epoch, gen, val+uint64(len(body)), nil)
					if len(body) < 4 {
						continue
					}
					payload := body[4:]
					if !seenAuth[slot] {
						seenAuth[slot] = true
						_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, testMySQLPkt(2, []byte{0x00, 0, 0, 2, 0, 0, 0}))
						continue
					}
					if len(payload) > 0 && payload[0] == 0x01 {
						_ = testNativeWireFrameWrite(x.Output, 104, 0, slot, x.Epoch, gen, 0, nil)
						continue
					}
					if len(payload) > 0 && payload[0] == 0x03 {
						q := string(payload[1:])
						if q == "XA RECOVER" {
							var resp bytes.Buffer
							resp.Write(testMySQLPkt(1, []byte{0x01}))
							resp.Write(testMySQLPkt(2, []byte{0x01, 'x'}))
							resp.Write(testMySQLPkt(3, []byte{0xfe, 0, 0, 2, 0}))
							resp.Write(testMySQLPkt(4, []byte{0xfe, 0, 0, 2, 0}))
							_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, resp.Bytes())
							continue
						}
						_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, testMySQLPkt(1, []byte{0x00, 0, 0, 2, 0, 0, 0}))
					}
				case 4: // PEER_EOF
					_ = testNativeWireFrameWrite(x.Output, 104, 0, slot, x.Epoch, gen, 0, nil)
				case 7: // STATS
					_ = testNativeWireFrameWrite(x.Output, 108, req, 0, x.Epoch, 0, 0, []byte(`{"sessions":[{"slot":0,"generation":1,"phase":"idle","status":2}]}`))
				case 8: // HOLD
					if val == 0 {
						if x.Stopped != nil {
							x.Stopped(errors.New("lost HOLD=0 reply"))
						}
						done <- errors.New("lost HOLD=0 reply")
						return
					}
					_ = testNativeWireFrameWrite(x.Output, 102, req, slot, x.Epoch, gen, 0, nil)
				case 6: // STOP
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

	svc, err := host.StartNative(ctx, nil, 0, io.Discard, "pub-keep-unusable", runner)
	if err != nil {
		t.Fatal(err)
	}
	db := &Database{server: svc, opts: Options{ShutdownTimeout: time.Second}}
	defer db.Close()

	c, err := svc.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	buf := make([]byte, 64)
	if _, err := c.Read(buf); err != nil {
		t.Fatal(err)
	}

	snap, err := db.Snapshot(ctx, SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if !rootCut.Load() {
		t.Fatal("expected SnapshotKeep to cut root before failing on HOLD=0")
	}
	if snap != nil {
		_ = snap.Close()
		t.Fatalf("expected nil snapshot when HOLD=0 release fails, got %v", snap)
	}
	var he *HostError
	if !errors.Is(err, ErrUnusable) || !errors.As(err, &he) || !he.Closed {
		t.Fatalf("expected closed ErrUnusable on HOLD=0 release failure, got %v", err)
	}
	if !db.Closed() || !errors.Is(db.Err(), ErrUnusable) {
		t.Fatalf("expected unusable closed database, closed=%v err=%v", db.Closed(), db.Err())
	}
}

type testBlockingWriteConn struct {
	net.Conn
	writeEntered  chan struct{}
	releaseWriter chan struct{}
	once          sync.Once
}

func (c *testBlockingWriteConn) Write(p []byte) (int, error) {
	c.once.Do(func() { close(c.writeEntered) })
	<-c.releaseWriter
	return c.Conn.Write(p)
}

type testSingleListener struct {
	ch     chan net.Conn
	closed chan struct{}
	once   sync.Once
}

func (l *testSingleListener) Accept() (net.Conn, error) {
	select {
	case c := <-l.ch:
		return c, nil
	case <-l.closed:
		return nil, net.ErrClosed
	}
}
func (l *testSingleListener) Close() error {
	l.once.Do(func() { close(l.closed) })
	return nil
}
func (l *testSingleListener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 1}
}

func TestPublicCloseAsyncWaitsForNativeWireRelaysNotMemoryRelease(t *testing.T) {
	ctx := closeTestContext(t)
	guestStopped := make(chan struct{})
	releaseMemory := make(chan struct{})
	writeEntered := make(chan struct{})
	releaseWriter := make(chan struct{})

	runner := func(x nativewire.Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			_ = testNativeWireFrameWrite(x.Output, 100, 0, 0, x.Epoch, 0, 0, []byte(`{"lifecycle_profile":3}`))
			var openSlot uint32
			var openGen uint64
			for {
				kind, req, slot, _, gen, val, _, err := testNativeWireFrameRead(x.Input)
				if err != nil {
					break
				}
				switch kind {
				case 1: // OPEN
					openSlot, openGen = slot, gen
					_ = testNativeWireFrameWrite(x.Output, 101, req, slot, x.Epoch, gen, 0, nil)
					_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, []byte("OUT"))
				case 6: // STOP
					if openGen != 0 {
						_ = testNativeWireFrameWrite(x.Output, 104, 0, openSlot, x.Epoch, openGen, 0, nil)
					}
					_ = testNativeWireFrameWrite(x.Output, 111, 0, 0, x.Epoch, 0, val, []byte(`{}`))
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

	b, err := nativewire.Start(ctx, nativewire.Config{Runner: runner, Build: "pub-close-async"})
	if err != nil {
		t.Fatal(err)
	}
	clientSide, serverRaw := net.Pipe()
	defer clientSide.Close()
	held := &testBlockingWriteConn{Conn: serverRaw, writeEntered: writeEntered, releaseWriter: releaseWriter}
	ln := &testSingleListener{ch: make(chan net.Conn, 1), closed: make(chan struct{})}
	ln.ch <- held
	if err := b.Serve(ln); err != nil {
		t.Fatal(err)
	}
	<-writeEntered

	db := &Database{server: &host.Native{Backend: b}, opts: Options{ShutdownTimeout: time.Second}}
	type asyncRes struct {
		h   *CloseHandle
		err error
	}
	resCh := make(chan asyncRes, 1)
	go func() {
		h, err := db.CloseAsync(ctx)
		resCh <- asyncRes{h, err}
	}()

	<-guestStopped
	select {
	case r := <-resCh:
		t.Fatalf("CloseAsync returned before held relay writer exited (active=%d, err=%v)", b.Active(), r.err)
	case <-time.After(50 * time.Millisecond):
	}
	if b.Active() != 1 {
		t.Fatalf("expected active=1 while writer held, got %d", b.Active())
	}

	close(releaseWriter)
	var r asyncRes
	select {
	case r = <-resCh:
	case <-time.After(2 * time.Second):
		t.Fatal("CloseAsync did not return after relays finished while memory release was gated")
	}
	if r.err != nil || r.h == nil {
		t.Fatalf("CloseAsync failed: handle=%v err=%v", r.h, r.err)
	}
	if b.Active() != 0 {
		t.Fatalf("expected active=0 when CloseAsync returns, got %d", b.Active())
	}
	if r.h.Disposed() {
		t.Fatal("expected handle.Disposed() == false while memory release is still gated")
	}

	close(releaseMemory)
	if err := r.h.Wait(ctx); err != nil {
		t.Fatalf("handle.Wait failed: %v", err)
	}
	if !r.h.Disposed() {
		t.Fatal("expected handle.Disposed() == true after memory release completes")
	}
}

func TestPublicCleanupFailureSnapshotKeepReturnsErrUnusableAndCloseReportsCause(t *testing.T) {
	ctx := closeTestContext(t)
	poisoned := make(chan struct{})
	runner := func(x nativewire.Execution) <-chan error {
		done := make(chan error, 1)
		go func() {
			_ = testNativeWireFrameWrite(x.Output, 100, 0, 0, x.Epoch, 0, 0, []byte(`{"lifecycle_profile":3}`))
			for {
				kind, req, slot, _, gen, val, _, err := testNativeWireFrameRead(x.Input)
				if err != nil {
					break
				}
				switch kind {
				case 1: // OPEN
					_ = testNativeWireFrameWrite(x.Output, 101, req, slot, x.Epoch, gen, 0, nil)
					_ = testNativeWireFrameWrite(x.Output, 103, 0, slot, x.Epoch, gen, 0, testMySQLPkt(0, []byte{0x0a, '1', '2', 0}))
				case 4: // PEER_EOF -> simulate cleanup_failed poison on session disconnect
					_ = testNativeWireFrameWrite(x.Output, 105, 0, 0, x.Epoch, 0, 0, []byte("cleanup_failed"))
					close(poisoned)
				case 6: // STOP
					_ = testNativeWireFrameWrite(x.Output, 111, 0, 0, x.Epoch, 0, val, []byte(`{}`))
					if x.Stopped != nil {
						x.Stopped(errors.New("exit 21"))
					}
					done <- errors.New("exit 21")
					return
				}
			}
			if x.Stopped != nil {
				x.Stopped(errors.New("exit 21"))
			}
			done <- errors.New("exit 21")
		}()
		return done
	}

	svc, err := host.StartNative(ctx, nil, 0, io.Discard, "pub-cleanup-failed", runner)
	if err != nil {
		t.Fatal(err)
	}
	db := &Database{server: svc, opts: Options{ShutdownTimeout: time.Second}}

	c, err := svc.DialContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	buf := make([]byte, 64)
	if _, err := c.Read(buf); err != nil {
		t.Fatal(err)
	}
	_ = c.Close()
	<-poisoned

	deadline := time.Now().Add(2 * time.Second)
	for svc.Failure() == nil && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}

	snap, err := db.Snapshot(ctx, SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if snap != nil {
		_ = snap.Close()
		t.Fatalf("expected nil snapshot after cleanup_failed, got %v", snap)
	}
	var he *HostError
	if !errors.Is(err, ErrUnusable) || !errors.As(err, &he) || !he.Closed || !strings.Contains(err.Error(), "cleanup_failed") {
		t.Fatalf("expected closed ErrUnusable(cleanup_failed) from SnapshotKeep, got %v", err)
	}

	closeErr := db.Close()
	if closeErr == nil || !strings.Contains(closeErr.Error(), "cleanup_failed") {
		t.Fatalf("expected Close to report cleanup_failed, got %v", closeErr)
	}
}
