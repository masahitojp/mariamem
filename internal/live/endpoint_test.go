package live

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net"
	"sync"
	"testing"
	"time"
)

type echoChild struct {
	listener net.Listener
	mu       sync.Mutex
	clients  map[net.Conn]bool
	workers  sync.WaitGroup
	closed   bool
	limit    int
	closeErr error
}

func echo(t *testing.T) *echoChild {
	t.Helper()
	ln, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	c := &echoChild{listener: ln, clients: map[net.Conn]bool{}, limit: 4}
	c.workers.Add(1)
	go func() {
		defer c.workers.Done()
		for {
			client, err := ln.Accept()
			if err != nil {
				return
			}
			c.mu.Lock()
			if c.closed {
				c.mu.Unlock()
				client.Close()
				return
			}
			c.clients[client] = true
			c.workers.Add(1)
			c.mu.Unlock()
			go func() {
				defer c.workers.Done()
				defer client.Close()
				_, _ = io.Copy(client, client)
				c.mu.Lock()
				delete(c.clients, client)
				c.mu.Unlock()
			}()
		}
	}()
	t.Cleanup(func() { _ = c.Close() })
	return c
}
func (c *echoChild) Address() string { return c.listener.Addr().String() }
func (c *echoChild) Capacity() int   { return c.limit }
func (c *echoChild) Failure() error  { return nil }
func (c *echoChild) WaitDisconnected(ctx context.Context) error {
	for {
		c.mu.Lock()
		n := len(c.clients)
		c.mu.Unlock()
		if n == 0 {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(time.Millisecond):
		}
	}
}
func (c *echoChild) Close() error {
	c.mu.Lock()
	if c.closeErr != nil {
		err := c.closeErr
		c.closeErr = nil
		c.mu.Unlock()
		return err
	}
	c.closed = true
	c.listener.Close()
	for conn := range c.clients {
		conn.Close()
	}
	c.mu.Unlock()
	c.workers.Wait()
	return nil
}
func newEndpoint(t *testing.T, f Factory) *Endpoint {
	t.Helper()
	e, err := New(context.Background(), f, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = e.Close() })
	return e
}
func connected(t *testing.T, e *Endpoint) net.Conn {
	t.Helper()
	c, err := net.DialTimeout("tcp4", net.JoinHostPort("127.0.0.1", fmtPort(e.Port())), time.Second)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { c.Close() })
	return c
}
func fmtPort(port int) string { return (&net.TCPAddr{Port: port}).String()[1:] }
func exchange(t *testing.T, c net.Conn, data []byte) {
	t.Helper()
	_ = c.SetDeadline(time.Now().Add(time.Second))
	if _, err := c.Write(data); err != nil {
		t.Fatal(err)
	}
	got := make([]byte, len(data))
	if _, err := io.ReadFull(c, got); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, data) {
		t.Fatal("byte stream changed")
	}
}
func waitActive(t *testing.T, e *Endpoint, n int) {
	t.Helper()
	deadline := time.Now().Add(time.Second)
	for e.Status().ActiveConnections != n {
		if time.Now().After(deadline) {
			t.Fatalf("active: %+v", e.Status())
		}
		time.Sleep(time.Millisecond)
	}
}
func TestBinaryBusyResetAndHalfClose(t *testing.T) {
	a, b := echo(t), echo(t)
	children := []Child{a, b}
	index := 0
	e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { c := children[index]; index++; return c, nil }})
	port := e.Port()
	c := connected(t, e)
	exchange(t, c, bytes.Repeat([]byte{0, 255, 128, 59}, 40000))
	if err := e.Reset(context.Background(), 5*time.Millisecond); err == nil {
		t.Fatal("idle connection accepted reset")
	}
	if e.Status().State != "ready" || e.Status().Generation != 0 {
		t.Fatal(e.Status())
	}
	exchange(t, c, []byte("old still usable"))
	_ = c.(*net.TCPConn).CloseWrite()
	if _, err := io.ReadAll(c); err != nil {
		t.Fatal(err)
	}
	c.Close()
	waitActive(t, e, 0)
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	if e.Port() != port || e.Status().Generation != 1 || !a.closed {
		t.Fatal("generation/endpoint changed incorrectly")
	}
	exchange(t, connected(t, e), []byte("new"))
	if err := e.Close(); err != nil {
		t.Fatal(err)
	}
	if err := e.Close(); err != nil {
		t.Fatal(err)
	}
	if e.Status().ActiveConnections != 0 || e.Status().State != "closed" || !b.closed {
		t.Fatal(e.Status())
	}
}
func TestFailureRefusesClientsAndRetry(t *testing.T) {
	a, b := echo(t), echo(t)
	index := 0
	injected := errors.New("injected fork failure")
	e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) {
		index++
		switch index {
		case 1:
			return a, nil
		case 2:
			return nil, injected
		default:
			return b, nil
		}
	}})
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, injected) {
		t.Fatal(err)
	}
	if e.Status().State != "failed" || a.closed {
		t.Fatal(e.Status())
	}
	c := connected(t, e)
	_ = c.SetReadDeadline(time.Now().Add(time.Second))
	if n, err := c.Read(make([]byte, 1)); n != 0 || err == nil {
		t.Fatal("failed endpoint admitted client")
	}
	c.Close()
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	exchange(t, connected(t, e), []byte("recovered"))
}
func TestCancellationOnBothSidesOfCommit(t *testing.T) {
	for _, after := range []bool{false, true} {
		t.Run(map[bool]string{false: "before", true: "after"}[after], func(t *testing.T) {
			a, b, c := echo(t), echo(t), echo(t)
			children := []Child{a, b, c}
			index := 0
			e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { child := children[index]; index++; return child, nil }})
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			if after {
				e.afterCommit = cancel
			} else {
				e.beforeCommit = cancel
			}
			err := e.Reset(ctx, time.Second)
			if after {
				if err != nil || e.Status().Generation != 1 || e.Status().State != "ready" {
					t.Fatalf("%v %+v", err, e.Status())
				}
			} else {
				if !errors.Is(err, context.Canceled) || e.Status().Generation != 0 || e.Status().State != "failed" || !b.closed {
					t.Fatalf("%v %+v", err, e.Status())
				}
				e.beforeCommit = nil
				if err := e.Reset(context.Background(), time.Second); err != nil {
					t.Fatal(err)
				}
				exchange(t, connected(t, e), []byte("retry after retired generation"))
			}
		})
	}
}
func TestBaselineClosePreconditionPreservesCurrentChild(t *testing.T) {
	child := echo(t)
	var closed bool
	e := newEndpoint(t, Factory{Check: func() error {
		if closed {
			return errors.New("snapshot closed")
		}
		return nil
	}, Start: func(context.Context) (Child, error) { return child, nil }})
	closed = true
	if err := e.Reset(context.Background(), time.Second); err == nil {
		t.Fatal("closed baseline accepted")
	}
	if child.closed || e.Status().State != "ready" || e.Status().Generation != 0 {
		t.Fatal(e.Status())
	}
	exchange(t, connected(t, e), []byte("unchanged"))
}
func TestCapacityAndQueuedCancellation(t *testing.T) {
	child := echo(t)
	child.limit = 1
	e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { return child, nil }})
	first := connected(t, e)
	exchange(t, first, []byte("held"))
	second := connected(t, e)
	_ = second.SetReadDeadline(time.Now().Add(time.Second))
	if n, err := second.Read(make([]byte, 1)); n != 0 || err == nil {
		t.Fatal("over capacity admitted")
	}
	second.Close()
	e.gate <- struct{}{}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := e.Reset(ctx, time.Second); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	<-e.gate
	if e.Status().State != "ready" {
		t.Fatal(e.Status())
	}
}
func TestConcurrentCloseWaitsForResetAndStopsWorkers(t *testing.T) {
	a, b := echo(t), echo(t)
	entered, release := make(chan struct{}), make(chan struct{})
	index := 0
	e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) {
		index++
		if index == 1 {
			return a, nil
		}
		close(entered)
		<-release
		return b, nil
	}})
	reset, closed := make(chan error, 1), make(chan error, 1)
	go func() { reset <- e.Reset(context.Background(), time.Second) }()
	<-entered
	if e.Status().State != "switching" {
		t.Fatal(e.Status())
	}
	go func() { closed <- e.Close() }()
	close(release)
	if err := <-reset; err != nil {
		t.Fatal(err)
	}
	if err := <-closed; err != nil {
		t.Fatal(err)
	}
	if !a.closed || !b.closed || e.Status().State != "closed" {
		t.Fatal(e.Status())
	}
}
func TestCleanupFailureIsRetainedAndCloseResultStable(t *testing.T) {
	a := echo(t)
	e := newEndpoint(t, Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { return a, nil }})
	cause := errors.New("cleanup failed")
	a.closeErr = cause
	err := e.Close()
	if !errors.Is(err, cause) || e.Status().CleanupError == "" {
		t.Fatal(err, e.Status())
	}
	if e.Close() != err {
		t.Fatal("close result lost")
	}
	_ = e.FinalCleanup()
	if !a.closed || len(e.pending) != 0 {
		t.Fatal("ownership not retried")
	}
}

func TestInFlightDialIsReservedAndCancelledByClose(t *testing.T) {
	child := echo(t)
	entered, stopped := make(chan struct{}), make(chan struct{})
	factory := Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { return child, nil }, dial: func(ctx context.Context, _ string) (net.Conn, error) {
		close(entered)
		<-ctx.Done()
		close(stopped)
		return nil, ctx.Err()
	}}
	e := newEndpoint(t, factory)
	_ = connected(t, e)
	<-entered
	if e.Status().ActiveConnections != 1 {
		t.Fatal("dial not reserved")
	}
	if err := e.Reset(context.Background(), time.Millisecond); err == nil {
		t.Fatal("pending dial bypassed drain")
	}
	if err := e.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case <-stopped:
	default:
		t.Fatal("dial not cancelled")
	}
	if e.Status().ActiveConnections != 0 {
		t.Fatal(e.Status())
	}
}

func TestCreationCleanupFailureReturnsOwnedTombstone(t *testing.T) {
	child := echo(t)
	child.limit = 0
	child.closeErr = errors.New("creation cleanup failure")
	e, err := New(context.Background(), Factory{Check: func() error { return nil }, Start: func(context.Context) (Child, error) { return child, nil }}, time.Second)
	if err == nil || e == nil || e.Status().State != "closed" || len(e.pending) != 1 {
		t.Fatal(e, err)
	}
	_ = e.FinalCleanup()
	if !child.closed || len(e.pending) != 0 {
		t.Fatal("creation cleanup owner lost")
	}
}
