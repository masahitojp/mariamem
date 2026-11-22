package nativewire

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// Execution is one runtime invocation. Runner must return promptly, report
// early failure without waiting for join, and send exactly one completion only
// after all native workers, descriptors and borrowed prepared mappings join.
// Capture approval is permission to freeze, not permission to release execution.
type Execution struct {
	Input    io.Reader
	Output   io.Writer
	Stderr   io.Writer
	Restore  []prepared.Entry
	Epoch    uint64
	Capture  *prepared.Capture
	Approval <-chan error
	Failure  func(error)
	Stopped  func(error)
}
type Runner func(Execution) <-chan error

type Config struct {
	Runner       Runner
	Build        string
	Restore      []prepared.Entry
	QueryTimeout time.Duration
	Stderr       io.Writer
	// RejectCapacity owns and closes a pre-login TCP connection. The host supplies
	// its existing bounded helper; core never imports the legacy packet decoder.
	RejectCapacity func(net.Conn)
	// CleanShutdownOnCapture forces innodb_fast_shutdown=1 before consuming capture.
	CleanShutdownOnCapture bool
}

// Backend owns one native instance, not a baseline, fork pool or Live generation.
// Failure is immediate; Done means execution, reader, accept and relay joins.
// It has no generatedgo dependency and does not select public routing.
type Backend struct {
	mu                           sync.Mutex
	writeMu                      sync.Mutex
	owner                        *Owner
	epoch                        uint64
	limit                        uint64
	build                        string
	cleanShutdownOnCapture       bool
	pending                      map[uint32]chan frame
	opening                      map[uint32]*session
	sessions                     map[key]*session
	sequence                     atomic.Uint32
	in, guestOut                 io.WriteCloser
	guestIn, out                 io.ReadCloser
	readyCh, failed, done        chan struct{}
	executionDone                chan struct{}
	readDone                     chan struct{}
	wg                           sync.WaitGroup
	listener                     net.Listener
	rejectCapacity               func(net.Conn)
	failure                      error
	stopping, checking, consumed bool
	approval                     chan error
	approvalOnce                 sync.Once
	capture                      prepared.Capture
	captureID                    uint64
	stopRequest                  uint32
	stopAcked, stopReceipt       bool
	operation                    chan struct{}
	stopOnce                     sync.Once
	stopSent                     chan struct{}
	disposer                     *disposal.Owner
	captureDebt                  error
	disconnectChanged            chan struct{}
	activityChanged              chan struct{}
	keepHold                     bool
	keepReleased                 chan struct{}
	stoppedCh                    chan struct{}
	stoppedOnce                  sync.Once
	stoppedErr                   error
	startTail                    *stderrTail
}

type stderrTail struct {
	mu      sync.Mutex
	active  bool
	data    []byte
	wrapped io.Writer
}

func (t *stderrTail) Write(p []byte) (int, error) {
	t.mu.Lock()
	if t.active {
		t.data = append(t.data, p...)
		if len(t.data) > 4096 {
			t.data = append(t.data[:0], t.data[len(t.data)-4096:]...)
		}
	}
	w := t.wrapped
	t.mu.Unlock()
	if w != nil {
		return w.Write(p)
	}
	return len(p), nil
}

func (t *stderrTail) stopAndText() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.active = false
	text := strings.TrimSpace(string(t.data))
	t.data = nil
	return text
}

var epochCounter atomic.Uint64

// Start returns no usable Backend on failure. Any still-running resources are
// retained by the typed disposal owner in the error, even if the caller drops it.
func Start(ctx context.Context, cfg Config) (*Backend, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	limit, err := TimeoutNanos(cfg.QueryTimeout)
	if err != nil {
		return nil, err
	}
	if cfg.Runner == nil || cfg.Build == "" {
		return nil, errors.New("native runner and build required")
	}
	epoch, err := Next64(&epochCounter)
	if err != nil {
		return nil, err
	}
	r := &Backend{owner: New(epoch), epoch: epoch, limit: limit, build: cfg.Build, cleanShutdownOnCapture: cfg.CleanShutdownOnCapture,
		pending: map[uint32]chan frame{}, opening: map[uint32]*session{}, sessions: map[key]*session{},
		readyCh: make(chan struct{}), failed: make(chan struct{}), done: make(chan struct{}), executionDone: make(chan struct{}), readDone: make(chan struct{}),
		approval: make(chan error, 1), operation: make(chan struct{}, 1), stopSent: make(chan struct{}), rejectCapacity: cfg.RejectCapacity,
		stoppedCh: make(chan struct{})}
	if r.rejectCapacity == nil {
		r.rejectCapacity = func(c net.Conn) { _ = c.Close() }
	}
	if os.Getenv("MARIAMEM_NATIVE_OS_PIPE") == "1" {
		r.guestIn, r.in, err = os.Pipe()
		if err != nil {
			return nil, err
		}
		r.out, r.guestOut, err = os.Pipe()
		if err != nil {
			return nil, errors.Join(err, r.guestIn.Close(), r.in.Close())
		}
	} else {
		r.guestIn, r.in = newBytePipe()
		r.out, r.guestOut = newBytePipe()
	}
	r.disposer = disposal.New(func(ctx context.Context) error {
		if err := disposal.Wait(ctx, r.done); err != nil {
			return err
		}
		r.capture.Discard()
		// All execution and host access is joined. Execution-side ends are already
		// closed by supervise to unblock the reader and pending writes.
		_ = r.in.Close()
		_ = r.out.Close()
		return nil
	})
	if cfg.Stderr == nil {
		cfg.Stderr = io.Discard
	}
	tail := &stderrTail{active: true, wrapped: cfg.Stderr}
	r.startTail = tail
	complete := cfg.Runner(Execution{r.guestIn, r.guestOut, tail, cfg.Restore, epoch, &r.capture, r.approval, func(e error) {
		// The runner callback cannot wait for a native/host join or pipe I/O.
		r.recordFailure(e)
		go r.abort()
	}, func(e error) {
		r.markStopped(e)
	}})
	r.wg.Add(1)
	go func() { defer r.wg.Done(); defer close(r.readDone); r.readLoop() }()
	if complete == nil {
		// Runner contract violation: execution ownership is unknown, so never invent
		// completion or release its input/restore resources.
		r.fail(errors.New("native runner returned nil completion"))
	} else {
		go r.supervise(complete)
	}
	select {
	case <-r.readyCh:
		if err := ctx.Err(); err != nil {
			return nil, r.startFailure(ctx, err)
		}
		if err := r.Failure(); err != nil {
			return nil, r.startFailure(ctx, err)
		}
		tail.stopAndText()
		return r, nil
	case <-r.failed:
		return nil, r.startFailure(ctx, r.Failure())
	case <-r.done:
		return nil, r.startFailure(ctx, errors.New("runtime ended before ready"))
	case <-ctx.Done():
		return nil, r.startFailure(ctx, ctx.Err())
	}
}

func (r *Backend) startFailure(ctx context.Context, cause error) error {
	r.fail(cause)
	// Completion/ctx and the early-failure channel can become ready together.
	// Returning a generic startup branch must not hide the first runtime cause.
	cause = r.Failure()
	var disposeErr error
	if ctx.Err() == nil {
		grace, cancel := context.WithTimeout(ctx, 2*time.Second)
		disposeErr = r.disposer.Retry(grace)
		cancel()
	} else {
		disposeErr = r.disposer.Probe()
	}
	if r.startTail != nil {
		if text := r.startTail.stopAndText(); text != "" {
			cause = fmt.Errorf("%w; stderr tail: %s", cause, text)
		}
	}
	if disposeErr != nil {
		return disposal.Retain(cause, disposeErr, r.disposer)
	}
	return cause
}
func (r *Backend) recordFailure(e error) {
	if e == nil {
		return
	}
	r.mu.Lock()
	if r.failure == nil {
		r.failure = e
		close(r.failed)
	}
	r.owner.StopLocked()
	r.notifyDisconnectLocked()
	r.notifyActivityLocked()
	r.mu.Unlock()
}
func (r *Backend) markStopped(e error) {
	r.stoppedOnce.Do(func() {
		r.stoppedErr = e
		close(r.stoppedCh)
	})
}
func (r *Backend) notifyDisconnectLocked() {
	if r.disconnectChanged != nil {
		close(r.disconnectChanged)
		r.disconnectChanged = nil
	}
}
func (r *Backend) notifyActivityLocked() {
	if r.activityChanged != nil {
		close(r.activityChanged)
		r.activityChanged = nil
	}
}
func (r *Backend) DisconnectState() (active int, changed, failed, done <-chan struct{}) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.disconnectChanged == nil {
		r.disconnectChanged = make(chan struct{})
	}
	return r.owner.CountLocked(), r.disconnectChanged, r.failed, r.done
}
func (r *Backend) fail(e error) { r.recordFailure(e); r.abort() }
func (r *Backend) abort() {
	r.resolve(errors.New("failed execution cannot approve capture"))
	r.stopIngress()
	_ = r.guestIn.Close() // cancel uncertain/partial host writes, no force kill
	r.disposer.Continue()
}
func (r *Backend) resolve(e error) { r.approvalOnce.Do(func() { r.approval <- e }) }
func (r *Backend) supervise(complete <-chan error) {
	err, ok := <-complete
	r.mu.Lock()
	expected := r.stopping || r.consumed
	r.mu.Unlock()
	if !ok {
		err = errors.New("native runner closed without completion result")
	}
	if err != nil {
		r.recordFailure(err)
	}
	r.stopIngress()
	_ = r.guestIn.Close()
	_ = r.guestOut.Close()
	// Drain the already-written control stream before inventing an unknown
	// exit cause. A buffered native POISON is more useful than generic EOF.
	<-r.readDone
	if !expected && r.Failure() == nil {
		r.recordFailure(errors.New("unexpected native execution end"))
	}
	close(r.executionDone)
	r.requestStop()
	<-r.stopSent
	r.wg.Wait()
	r.mu.Lock()
	r.owner.DisposeLocked()
	r.sessions = map[key]*session{}
	r.notifyDisconnectLocked()
	r.notifyActivityLocked()
	r.mu.Unlock()
	r.markStopped(r.Failure())
	close(r.done)
	if r.Failure() != nil {
		r.disposer.Continue()
	}
}
func (r *Backend) stopIngress() {
	r.mu.Lock()
	r.stopping = true
	r.owner.StopLocked()
	r.notifyDisconnectLocked()
	r.notifyActivityLocked()
	if r.keepReleased != nil {
		close(r.keepReleased)
		r.keepReleased = nil
		r.keepHold = false
	}
	listener := r.listener
	all := make([]*session, 0, len(r.sessions))
	for _, s := range r.sessions {
		all = append(all, s)
	}
	r.mu.Unlock()
	if listener != nil {
		_ = listener.Close()
	}
	for _, s := range all {
		s.close()
	}
}
func (r *Backend) requestStop() {
	r.stopOnce.Do(func() { go func() { defer close(r.stopSent); _ = r.send(frame{kind: kindStop}) }() })
}
func (r *Backend) Failure() error         { r.mu.Lock(); defer r.mu.Unlock(); return r.failure }
func (r *Backend) Done() <-chan struct{}  { return r.done }
func (r *Backend) Capacity() int          { return Capacity }
func (r *Backend) Active() int            { r.mu.Lock(); defer r.mu.Unlock(); return r.owner.CountLocked() }
func (r *Backend) CaptureDebt() error     { r.mu.Lock(); defer r.mu.Unlock(); return r.captureDebt }
func (r *Backend) DisposalComplete() bool { return r.disposer.Complete() }
func (r *Backend) SnapshotCapable() bool  { return r.build != "" }
func (r *Backend) Port() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.listener == nil {
		return 0
	}
	if a, ok := r.listener.Addr().(*net.TCPAddr); ok {
		return a.Port
	}
	return 0
}
func (r *Backend) Busy() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, s := range r.sessions {
		if s.phase != "idle" {
			return true
		}
	}
	return false
}
func (r *Backend) Close(ctx context.Context) error {
	return r.CloseWithStopped(ctx, nil)
}

func (r *Backend) CloseWithStopped(ctx context.Context, notify func(error)) error {
	r.resolve(errors.New("ordinary close cannot approve capture"))
	r.stopIngress()
	r.requestStop()
	if notify != nil {
		notified := make(chan struct{})
		go func() {
			stopErr := disposal.Wait(ctx, r.stoppedCh)
			if stopErr == nil {
				stopErr = errors.Join(r.stoppedErr, r.Failure())
			}
			notify(stopErr)
			close(notified)
		}()
		defer func() { <-notified }()
	}
	err := r.disposer.Retry(ctx)
	cause := r.Failure()
	if err != nil {
		// Cancellation ends the host write, not the still-running native worker.
		_ = r.guestIn.Close()
		return disposal.Retain(cause, err, r.disposer)
	}
	return cause
}

func (r *Backend) send(f frame) error {
	f.epoch = r.epoch
	r.writeMu.Lock()
	defer r.writeMu.Unlock()
	return writeFrame(r.in, f)
}

type unsentControl struct{ error }

func (e *unsentControl) Unwrap() error { return e.error }
func (r *Backend) sendContext(ctx context.Context, f frame) error {
	if e := ctx.Err(); e != nil {
		return &unsentControl{e}
	}
	done := make(chan error, 1)
	go func() { done <- r.send(f) }()
	select {
	case e := <-done:
		return e
	case <-ctx.Done():
		_ = r.guestIn.Close()
		<-done
		return ctx.Err()
	case <-r.failed:
		_ = r.guestIn.Close()
		<-done
		return r.Failure()
	}
}
func (r *Backend) rpc(f frame, initial ...*session) (frame, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	return r.rpcContext(ctx, f, initial...)
}
func (r *Backend) rpcContext(ctx context.Context, f frame, initial ...*session) (frame, error) {
	id, err := Next32(&r.sequence)
	if err != nil {
		r.fail(err)
		return frame{}, err
	}
	f.request = id
	ch := make(chan frame, 1)
	r.mu.Lock()
	r.pending[id] = ch
	if f.kind == kindCaptureStop {
		r.stopRequest = id
	}
	if len(initial) > 0 {
		r.opening[id] = initial[0]
	}
	r.mu.Unlock()
	defer func() { r.mu.Lock(); delete(r.pending, id); delete(r.opening, id); r.mu.Unlock() }()
	if e := r.sendContext(ctx, f); e != nil {
		return frame{}, e
	}
	select {
	case answer := <-ch:
		return answer, nil
	case <-r.failed:
		return frame{}, r.Failure()
	case <-r.executionDone:
		return frame{}, fmt.Errorf("native execution ended: %w", ErrClosed)
	case <-ctx.Done():
		return frame{}, ctx.Err()
	}
}
func (r *Backend) readLoop() {
	for {
		f, e := readFrame(r.out)
		if e != nil {
			r.mu.Lock()
			normal := r.stopping
			r.mu.Unlock()
			if !normal {
				r.fail(e)
			}
			r.resolve(fmt.Errorf("capture transport ended: %w", e))
			return
		}
		if !r.receiveFrame(f) {
			return
		}
	}
}
func (r *Backend) receiveFrame(f frame) bool {
	if f.epoch != r.epoch {
		r.fail(ErrIdentity)
		return false
	}
	if f.kind == kindCaptureStopped {
		r.mu.Lock()
		valid := r.consumed && r.captureID != 0 && f.value == r.captureID && f.request == r.stopRequest && !r.stopReceipt
		if valid {
			r.stopReceipt = true
		}
		acked := r.stopAcked
		r.mu.Unlock()
		if !valid {
			r.fail(errors.New("wrong capture receipt"))
			return false
		}
		if acked {
			r.resolve(nil)
		}
		return true
	}
	r.mu.Lock()
	initial := r.opening[f.request]
	var err error
	if f.kind == kindOpened {
		if initial == nil {
			err = errors.New("OPENED without request")
		} else {
			err = r.owner.OpenedLocked(initial.lease, Token{r.epoch, f.slot, f.generation})
		}
	}
	if f.kind == kindRejected && initial != nil {
		if f.value != 4 {
			err = errors.New("unexpected native OPEN rejection")
		} else {
			err = r.owner.RejectLocked(initial.lease, Token{r.epoch, f.slot, f.generation})
		}
	}
	ch := r.pending[f.request]
	s := r.sessions[key{f.slot, f.generation}]
	stale := r.owner.StaleLocked(Token{r.epoch, f.slot, f.generation})
	if f.kind == kindState && s != nil {
		s.phase = string(f.body)
		r.notifyActivityLocked()
	}
	r.mu.Unlock()
	if err != nil {
		r.fail(err)
		return false
	}
	if ch != nil {
		select {
		case ch <- f:
		default:
			r.fail(errors.New("duplicate native control reply"))
			return false
		}
		return true
	}
	switch f.kind {
	case kindReady:
		var profile struct {
			Lifecycle int `json:"lifecycle_profile"`
		}
		if json.Unmarshal(f.body, &profile) != nil || profile.Lifecycle != 3 {
			r.fail(errors.New("wrong lifecycle profile"))
			return false
		}
		select {
		case <-r.readyCh:
			r.fail(errors.New("duplicate native ready"))
			return false
		default:
			close(r.readyCh)
		}
	case kindRaw:
		if s == nil {
			if stale {
				return true
			}
			r.fail(errors.New("output without session"))
			return false
		}
		select {
		case s.output <- f:
		case <-s.ended:
		default:
			r.fail(errors.New("bounded host output queue overflow"))
			return false
		}
	case kindCredit:
		if s != nil {
			s.mu.Lock()
			valid := f.value >= s.consumed && f.value <= s.sent
			if valid {
				s.consumed = f.value
				s.cv.Broadcast()
			}
			s.mu.Unlock()
			if !valid {
				r.fail(errors.New("invalid native input credit"))
				return false
			}
		}
	case kindRetired:
		if s != nil {
			r.nativeRetired(s)
		}
	case kindPoison:
		e := fmt.Errorf("guest poison: %s", f.body)
		if string(f.body) == "deadline" || string(f.body) == "deadline_injected" {
			e = fmt.Errorf("%w: %s", context.DeadlineExceeded, f.body)
		}
		r.fail(e)
		return false
	}
	return true
}
