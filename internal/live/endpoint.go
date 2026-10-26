// Package live owns a stable TCP endpoint over private replaceable children.
// It transports bytes without interpreting SQL or retaining SQL sessions on reset.
package live

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
)

type Child interface {
	Address() string
	Capacity() int
	WaitDisconnected(context.Context) error
	Close() error
	Failure() error
}
type Factory struct {
	dial  func(context.Context, string) (net.Conn, error)
	Check func() error
	Start func(context.Context) (Child, error)
}
type Status struct {
	State             string `json:"state"`
	Generation        uint64 `json:"generation"`
	ActiveConnections int    `json:"active_connections"`
	CleanupError      string `json:"cleanup_error,omitempty"`
}
type connection struct {
	client, upstream net.Conn
	cancel           context.CancelFunc
}
type Endpoint struct {
	mu       sync.Mutex
	gate     chan struct{}
	factory  Factory
	listener net.Listener
	accepted chan struct{}
	workers  sync.WaitGroup
	changed  chan struct{}
	clients  map[*connection]struct{}
	child    Child
	retired  bool
	pending  []Child
	status   Status
	shutdown time.Duration
	closeErr error
	// Commit barriers are private deterministic test seams; nil in production.
	beforeCommit, afterCommit func()
}

func failure(code, stage string, err error) error { return diagnostic.Wrap(code, stage, err) }
func New(ctx context.Context, factory Factory, shutdown time.Duration) (*Endpoint, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if shutdown <= 0 {
		return nil, errors.New("shutdown timeout must be positive")
	}
	if err := factory.Check(); err != nil {
		return nil, failure("closed", "live_precondition", err)
	}
	child, err := factory.Start(ctx)
	if err != nil {
		return nil, err
	}
	if child.Capacity() <= 0 {
		return aborted(child, errors.New("invalid child capacity"))
	}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return aborted(child, err)
	}
	if err = ctx.Err(); err != nil {
		listener.Close()
		return aborted(child, err)
	}
	e := &Endpoint{gate: make(chan struct{}, 1), factory: factory, listener: listener, accepted: make(chan struct{}), changed: make(chan struct{}), clients: map[*connection]struct{}{}, child: child, status: Status{State: "ready"}, shutdown: shutdown}
	go e.accept()
	return e, nil
}

// aborted returns a cleanup-only closed handle when child cleanup fails.
// Owners must retain this tombstone through final cleanup rather than lose it.
func aborted(child Child, cause error) (*Endpoint, error) {
	cleanup := child.Close()
	err := errors.Join(cause, cleanup)
	if cleanup == nil {
		return nil, err
	}
	e := &Endpoint{gate: make(chan struct{}, 1), pending: []Child{child}, status: Status{State: "closed", CleanupError: cleanup.Error()}, closeErr: err}
	return e, err
}
func (e *Endpoint) Port() int { return e.listener.Addr().(*net.TCPAddr).Port }
func (e *Endpoint) Status() Status {
	e.mu.Lock()
	defer e.mu.Unlock()
	s := e.status
	s.ActiveConnections = len(e.clients)
	if s.State == "ready" && e.child.Failure() != nil {
		s.State = "failed"
	}
	return s
}
func (e *Endpoint) signal() { close(e.changed); e.changed = make(chan struct{}) }
func (e *Endpoint) accept() {
	defer close(e.accepted)
	for {
		client, err := e.listener.Accept()
		if err != nil {
			return
		}
		e.mu.Lock()
		if e.status.State != "ready" || e.child.Failure() != nil || len(e.clients) >= e.child.Capacity() {
			e.mu.Unlock()
			client.Close()
			continue
		}
		ctx, cancel := context.WithCancel(context.Background())
		c := &connection{client: client, cancel: cancel}
		e.clients[c] = struct{}{}
		address := e.child.Address()
		e.workers.Add(1)
		e.mu.Unlock()
		go e.forward(ctx, c, address)
	}
}
func (e *Endpoint) forward(ctx context.Context, c *connection, address string) {
	defer e.workers.Done()
	defer func() {
		c.cancel()
		e.mu.Lock()
		if c.upstream != nil {
			c.upstream.Close()
		}
		c.client.Close()
		delete(e.clients, c)
		e.signal()
		e.mu.Unlock()
	}()
	dial := e.factory.dial
	if dial == nil {
		dial = func(ctx context.Context, address string) (net.Conn, error) {
			return (&net.Dialer{Timeout: 5 * time.Second}).DialContext(ctx, "tcp4", address)
		}
	}
	upstream, err := dial(ctx, address)
	if err != nil {
		return
	}
	e.mu.Lock()
	c.upstream = upstream
	closed := e.status.State == "closed"
	e.mu.Unlock()
	if closed {
		return
	}
	var copies sync.WaitGroup
	copies.Add(2)
	copyStream := func(dst, src net.Conn) {
		defer copies.Done()
		_, err := io.Copy(dst, src)
		if err != nil {
			dst.Close()
			src.Close()
			return
		}
		if tcp, ok := dst.(*net.TCPConn); ok {
			_ = tcp.CloseWrite()
		} else {
			_ = dst.Close()
		}
	}
	go copyStream(upstream, c.client)
	go copyStream(c.client, upstream)
	copies.Wait()
}
func (e *Endpoint) lock(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	select {
	case e.gate <- struct{}{}:
		if err := ctx.Err(); err != nil {
			<-e.gate
			return err
		}
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
func (e *Endpoint) cleanup(children []Child) error {
	var err error
	for _, child := range children {
		if child != nil {
			if cause := child.Close(); cause != nil {
				e.pending = append(e.pending, child)
				err = errors.Join(err, cause)
			}
		}
	}
	if err != nil {
		e.mu.Lock()
		e.status.CleanupError = err.Error()
		e.mu.Unlock()
	}
	return err
}
func (e *Endpoint) Reset(ctx context.Context, drain time.Duration) error {
	if drain <= 0 {
		return failure("invalid_options", "live_precondition", errors.New("drain timeout must be positive"))
	}
	if err := e.lock(ctx); err != nil {
		return err
	}
	defer func() { <-e.gate }()
	e.mu.Lock()
	previous := e.status.State
	e.mu.Unlock()
	if previous == "closed" {
		return failure("closed", "live_precondition", errors.New("live is closed"))
	}
	if err := e.factory.Check(); err != nil {
		return failure("closed", "live_precondition", err)
	}
	e.mu.Lock()
	e.status.State = "draining"
	e.signal()
	timer := time.NewTimer(drain)
	defer timer.Stop()
	for len(e.clients) > 0 {
		changed := e.changed
		e.mu.Unlock()
		var err error
		select {
		case <-changed:
		case <-ctx.Done():
			err = failure("timeout", "live_drain", ctx.Err())
		case <-timer.C:
			err = failure("busy", "live_drain", errors.New("close all physical SQL connections before reset"))
		}
		e.mu.Lock()
		if err != nil {
			e.status.State = previous
			e.signal()
			e.mu.Unlock()
			return err
		}
	}
	if err := ctx.Err(); err != nil {
		e.status.State = previous
		e.mu.Unlock()
		return err
	}
	e.status.State = "switching"
	e.mu.Unlock()
	pending := e.pending
	e.pending = nil
	if err := e.cleanup(pending); err != nil {
		return e.failed(err, nil)
	}
	candidate, err := e.factory.Start(ctx)
	if err != nil {
		return e.failed(err, nil)
	}
	if candidate.Capacity() <= 0 {
		return e.failed(errors.New("invalid child capacity"), candidate)
	}
	// Drivers may have closed the relay while the backend still acknowledges
	// session cleanup. This wait is bounded even without a caller deadline.
	cleanupCtx, cancel := context.WithTimeout(context.Background(), e.shutdown)
	if !e.retired {
		err = e.child.WaitDisconnected(cleanupCtx)
		if err == nil {
			err = e.child.Close()
			if err == nil {
				e.retired = true
			}
		}
	}
	cancel()
	if err != nil {
		return e.failed(err, candidate)
	}
	if e.beforeCommit != nil {
		e.beforeCommit()
	}
	e.mu.Lock()
	err = ctx.Err()
	if err == nil {
		e.child = candidate
		e.retired = false
		e.status.State = "ready"
		e.status.Generation++
		e.status.CleanupError = ""
		e.signal()
	}
	e.mu.Unlock()
	if err != nil {
		return e.failed(err, candidate)
	}
	if e.afterCommit != nil {
		e.afterCommit()
	}
	return nil
}
func (e *Endpoint) failed(err error, candidate Child) error {
	cleanup := e.cleanup([]Child{candidate})
	e.mu.Lock()
	e.status.State = "failed"
	e.signal()
	e.mu.Unlock()
	return failure("unusable", "live_replace", errors.Join(err, cleanup))
}
func (e *Endpoint) Close() error {
	_ = e.lock(context.Background())
	defer func() { <-e.gate }()
	e.mu.Lock()
	if e.status.State == "closed" {
		e.mu.Unlock()
		return e.closeErr
	}
	e.status.State = "closed"
	e.signal()
	e.listener.Close()
	for c := range e.clients {
		c.cancel()
		c.client.Close()
		if c.upstream != nil {
			c.upstream.Close()
		}
	}
	e.mu.Unlock()
	<-e.accepted
	done := make(chan struct{})
	go func() { e.workers.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(e.shutdown):
		e.closeErr = fmt.Errorf("live relay cleanup timed out")
	}
	pending := e.pending
	e.pending = nil
	e.closeErr = errors.Join(e.closeErr, e.cleanup(append(pending, e.child)))
	return e.closeErr
}

// FinalCleanup retains and retries unresolved owned children at host shutdown.
// The public Close result remains stable even if later cleanup succeeds.
func (e *Endpoint) FinalCleanup() error {
	first := e.Close()
	_ = e.lock(context.Background())
	defer func() { <-e.gate }()
	pending := e.pending
	e.pending = nil
	return errors.Join(first, e.cleanup(pending))
}
