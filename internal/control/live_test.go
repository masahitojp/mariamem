package control

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	endpoint "github.com/masahitojp/mariamem/internal/live"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

type lifecycleChild struct {
	listener net.Listener
	done     chan struct{}
	once     sync.Once
}

func (c *lifecycleChild) Address() string                        { return c.listener.Addr().String() }
func (c *lifecycleChild) Capacity() int                          { return 1 }
func (c *lifecycleChild) Failure() error                         { return nil }
func (c *lifecycleChild) WaitDisconnected(context.Context) error { return nil }
func (c *lifecycleChild) Close() error {
	c.once.Do(func() { c.listener.Close(); close(c.done) })
	return nil
}
func managedLive(t *testing.T, m *manager) (uint64, *lifecycleChild) {
	t.Helper()
	ln, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	child := &lifecycleChild{listener: ln, done: make(chan struct{})}
	t.Cleanup(func() { child.Close() })
	live, err := endpoint.New(context.Background(), endpoint.Factory{Check: func() error { return nil }, Start: func(context.Context) (endpoint.Child, error) { return child, nil }}, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { live.Close() })
	m.mu.Lock()
	id := m.next()
	m.lives[id] = live
	m.mu.Unlock()
	return id, child
}
func TestCommittedResetReplyWinsOnlyForLiveReset(t *testing.T) {
	for _, op := range []string{"live_reset", "ordinary"} {
		t.Run(op, func(t *testing.T) {
			m := newManager()
			in, writer := io.Pipe()
			reader, out := io.Pipe()
			entered := make(chan struct{})
			done := make(chan error, 1)
			operation := func(ctx context.Context, r Request) (map[string]any, error) {
				close(entered)
				<-ctx.Done()
				return map[string]any{"live_committed": true}, nil
			}
			go func() { done <- runWith(context.Background(), in, out, m, operation); out.Close() }()
			dec := json.NewDecoder(reader)
			enc := json.NewEncoder(writer)
			var reply map[string]any
			if err := dec.Decode(&reply); err != nil {
				t.Fatal(err)
			}
			enc.Encode(Request{ID: 1, Op: op})
			<-entered
			enc.Encode(Request{Op: "cancel", Target: 1})
			if err := dec.Decode(&reply); err != nil {
				t.Fatal(err)
			}
			if reply["ok"] != (op == "live_reset") {
				t.Fatal(reply)
			}
			writer.Close()
			if err := <-done; err != nil {
				t.Fatal(err)
			}
			reader.Close()
		})
	}
}
func TestCancelledCreatedLiveIsCollectedByControl(t *testing.T) {
	m := newManager()
	id, child := managedLive(t, m)
	in, writer := io.Pipe()
	reader, out := io.Pipe()
	entered := make(chan struct{})
	done := make(chan error, 1)
	operation := func(ctx context.Context, r Request) (map[string]any, error) {
		close(entered)
		<-ctx.Done()
		return map[string]any{"live": map[string]any{"handle": id}}, nil
	}
	go func() { done <- runWith(context.Background(), in, out, m, operation); out.Close() }()
	enc := json.NewEncoder(writer)
	dec := json.NewDecoder(reader)
	var reply map[string]any
	dec.Decode(&reply)
	enc.Encode(Request{ID: 1, Op: "live_create"})
	<-entered
	enc.Encode(Request{Op: "cancel", Target: 1})
	dec.Decode(&reply)
	if reply["ok"] != false || reply["live"] != nil {
		t.Fatal(reply)
	}
	select {
	case <-child.done:
	default:
		t.Fatal("late child not closed")
	}
	m.mu.Lock()
	n := len(m.lives)
	m.mu.Unlock()
	if n != 0 {
		t.Fatal("live handle leaked")
	}
	writer.Close()
	if err := <-done; err != nil {
		t.Fatal(err)
	}
	reader.Close()
}
func TestLiveOnlyShutdownIsBusyAndEOFDisposesIt(t *testing.T) {
	m := newManager()
	_, child := managedLive(t, m)
	in, writer := io.Pipe()
	reader, out := io.Pipe()
	done := make(chan error, 1)
	go func() { done <- runWith(context.Background(), in, out, m, nil); out.Close() }()
	dec := json.NewDecoder(reader)
	var reply map[string]any
	dec.Decode(&reply)
	caps := reply["capabilities"].([]any)
	if len(caps) != 2 || caps[0] != "live-v1" || caps[1] != "fork-limit-v1" {
		t.Fatal(reply)
	}
	json.NewEncoder(writer).Encode(Request{ID: 1, Op: "shutdown"})
	dec.Decode(&reply)
	if reply["ok"] != false {
		t.Fatal("shutdown ignored live owner", reply)
	}
	writer.Close()
	if err := <-done; err != nil {
		t.Fatal(err)
	}
	select {
	case <-child.done:
	default:
		t.Fatal("EOF did not close live")
	}
	reader.Close()
}

// Use the real adapter and a real removal failure, after backend shutdown.
type disposedLogChild struct{ *liveChild }

func (c disposedLogChild) Address() string { return "127.0.0.1:1" }
func (c disposedLogChild) Capacity() int   { return 1 }
func (c disposedLogChild) Failure() error  { return nil }

func TestManagerRetriesLiveLogRemovalAfterCloseFailure(t *testing.T) {
	path := filepath.Join(t.TempDir(), "child.log")
	log, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer log.Close()
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(path, 0700); err != nil {
		t.Fatal(err)
	}
	blocker := filepath.Join(path, "blocker")
	if err := os.WriteFile(blocker, []byte("block removal"), 0600); err != nil {
		t.Fatal(err)
	}
	child := disposedLogChild{&liveChild{db: &db{closed: true, log: log, logPath: path, shutdown: time.Second}}}
	e, err := endpoint.New(context.Background(), endpoint.Factory{Check: func() error { return nil }, Start: func(context.Context) (endpoint.Child, error) { return child, nil }}, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer e.FinalCleanup()
	m := newManager()
	m.lives[1] = e
	_, first := m.callLive(context.Background(), Request{Op: "live_close", Handle: 1})
	if first == nil || m.lives[1] != e {
		t.Fatal(first, m.lives)
	}
	if err := os.Remove(blocker); err != nil {
		t.Fatal(err)
	}
	if err := m.cleanup(); err == nil {
		t.Fatal("lost original cleanup error")
	}
	if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatal(err)
	}
	if again := e.Close(); again == nil {
		t.Fatal("lost stored Close result")
	}
}

func adapterCapacityEndpoint(t *testing.T, b *baseline, children ...disposedLogChild) (*manager, *int) {
	t.Helper()
	index := 0
	factory := endpoint.Factory{Check: func() error {
		b.mu.RLock()
		defer b.mu.RUnlock()
		if b.closed {
			return forklimit.ErrClosed
		}
		return nil
	}, Reserve: func(ctx context.Context, recover bool) (*endpoint.Reservation, error) {
		l, err := b.forkLimit().TryAcquire(recover)
		if err != nil {
			return nil, err
		}
		return &endpoint.Reservation{Cancel: l.Cancel, Start: func(context.Context) (endpoint.Child, error) {
			if err := l.Activate(); err != nil {
				return nil, err
			}
			if index == len(children) {
				l.Settle(nil)
				return nil, errors.New("unexpected extra child")
			}
			child := children[index]
			index++
			child.db.lease = l
			return child, nil
		}}, nil
	}}
	e, err := endpoint.New(context.Background(), factory, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { e.FinalCleanup() })
	m := newManager()
	m.lives[1] = e
	return m, &index
}

func adapterCleanupChild(t *testing.T, blocked bool) (disposedLogChild, string) {
	t.Helper()
	d := &db{closed: true, shutdown: time.Second}
	marker := ""
	if blocked {
		d.logPath = filepath.Join(t.TempDir(), "retained.log")
		if err := os.Mkdir(d.logPath, 0700); err != nil {
			t.Fatal(err)
		}
		marker = filepath.Join(d.logPath, "blocker")
		if err := os.WriteFile(marker, []byte("incomplete cleanup"), 0600); err != nil {
			t.Fatal(err)
		}
		// Execution is already disposed; this real filesystem cleanup is not.
		d.closeErr = disposal.CleanupAfter(nil, func() error { return removeLog(d.logPath) })
	}
	return disposedLogChild{&liveChild{db: d}}, marker
}

func TestControlAdapterCapTwoRecoveryJoinsBothCleanupOwners(t *testing.T) {
	p, _ := forklimit.New(2)
	a, oldMarker := adapterCleanupChild(t, true)
	b, newMarker := adapterCleanupChild(t, true)
	c, _ := adapterCleanupChild(t, false)
	m, starts := adapterCapacityEndpoint(t, &baseline{limit: p}, a, b, c)
	r := Request{Op: "live_reset", Handle: 1, Timeout: "1s", DrainTimeout: "1s"}
	_, firstErr := m.callLive(context.Background(), r)
	if firstErr == nil {
		t.Fatal("two cleanup failures lost")
	}
	// Retain and retry the full original controlled error as well as the DB's
	// owner, so the test does not strand dependency-wrapper continuations.
	t.Cleanup(func() {
		if err := disposal.Retry(context.Background(), firstErr); err != nil {
			t.Error(err)
		}
	})
	if *starts != 2 || m.lives[1].Status().Generation != 0 || m.lives[1].Status().State != "failed" {
		t.Fatal(*starts, m.lives[1].Status())
	}
	if _, err := p.TryAcquire(true); !errors.Is(err, forklimit.ErrCleanup) {
		t.Fatal("unresolved debt forgiven", err)
	}
	if err := os.Remove(oldMarker); err != nil {
		t.Fatal(err)
	}
	if _, err := m.callLive(context.Background(), r); err == nil {
		t.Fatal("candidate cleanup retry failure lost")
	}
	if *starts != 2 {
		t.Fatal("started while debt remained", *starts)
	}
	if err := os.Remove(newMarker); err != nil {
		t.Fatal(err)
	}
	if _, err := m.callLive(context.Background(), r); err != nil {
		t.Fatal(err)
	}
	if *starts != 3 || m.lives[1].Status().Generation != 1 || m.lives[1].Status().State != "ready" {
		t.Fatal(*starts, m.lives[1].Status())
	}
	extra, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	defer extra.Cancel()
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
		t.Fatal("cap2 exceeded", err)
	}
}

func TestControlAdapterRecoveryCannotForgiveUnrelatedDebtOrParentClose(t *testing.T) {
	p, _ := forklimit.New(2)
	base := &baseline{limit: p}
	a, _ := adapterCleanupChild(t, false)
	b, _ := adapterCleanupChild(t, false)
	m, starts := adapterCapacityEndpoint(t, base, a, b)
	other, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if err := other.Activate(); err != nil {
		t.Fatal(err)
	}
	cause := errors.New("unrelated unresolved cleanup")
	other.Settle(cause)
	r := Request{Op: "live_reset", Handle: 1, Timeout: "1s", DrainTimeout: "1s"}
	if _, err := m.callLive(context.Background(), r); !errors.Is(err, cause) {
		t.Fatal(err)
	}
	if *starts != 1 || m.lives[1].Status().State != "ready" {
		t.Fatal("healthy child changed")
	}
	other.Settle(nil)
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrCleanup) {
		t.Fatal("automatically reopened", err)
	}
	if _, err := m.callLive(context.Background(), r); err != nil {
		t.Fatal(err)
	}
	base.mu.Lock()
	base.closed = true
	p.Close()
	base.mu.Unlock()
	if _, err := m.callLive(context.Background(), r); !errors.Is(err, forklimit.ErrClosed) {
		t.Fatal(err)
	}
	if *starts != 2 || m.lives[1].Status().Generation != 1 {
		t.Fatal(*starts, m.lives[1].Status())
	}
}
