package mariamem

import (
	"context"
	"database/sql"
	"errors"
	"github.com/go-sql-driver/mysql"
	"sync"
	"testing"
	"time"
)

type notifyFake struct {
	fakeBackend
	mu                    sync.Mutex
	n                     int
	changed, failed, done chan struct{}
	cause                 error
	registered            chan struct{}
	afterSnapshot         func()
}

func newNotifyFake(n int) *notifyFake {
	return &notifyFake{n: n, changed: make(chan struct{}), failed: make(chan struct{}), done: make(chan struct{}), registered: make(chan struct{}, 64)}
}
func (f *notifyFake) Active() int    { f.mu.Lock(); defer f.mu.Unlock(); return f.n }
func (f *notifyFake) Failure() error { f.mu.Lock(); defer f.mu.Unlock(); return f.cause }
func (f *notifyFake) DisconnectState() (int, <-chan struct{}, <-chan struct{}, <-chan struct{}) {
	f.mu.Lock()
	n, ch, failed, done := f.n, f.changed, f.failed, f.done
	hook := f.afterSnapshot
	f.afterSnapshot = nil
	f.mu.Unlock()
	f.registered <- struct{}{}
	if hook != nil {
		hook()
	}
	return n, ch, failed, done
}
func (f *notifyFake) set(n int) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.n = n
	close(f.changed)
	f.changed = make(chan struct{})
}
func (f *notifyFake) Close(context.Context) error { f.set(f.Active()); return nil }
func notifyResult(t *testing.T, ch <-chan error) error {
	t.Helper()
	select {
	case e := <-ch:
		return e
	case <-time.After(time.Second):
		t.Fatal("wait stuck")
		return nil
	}
}
func notifyRegistered(t *testing.T, f *notifyFake) {
	t.Helper()
	select {
	case <-f.registered:
	case <-time.After(time.Second):
		t.Fatal("no state registration")
	}
}
func TestWaitDisconnectedNotifications(t *testing.T) {
	t.Run("active_cancel_keeps_database", func(t *testing.T) {
		f := newNotifyFake(1)
		db := &Database{server: f}
		ctx, cancel := context.WithCancel(context.Background())
		ch := make(chan error, 1)
		go func() { ch <- db.WaitDisconnected(ctx) }()
		notifyRegistered(t, f)
		select {
		case e := <-ch:
			t.Fatalf("early success %v", e)
		default:
		}
		cancel()
		if e := notifyResult(t, ch); !errors.Is(e, context.Canceled) {
			t.Fatal(e)
		}
		if db.Err() != nil || f.Active() != 1 {
			t.Fatal("cancel invalidated DB")
		}
	})
	t.Run("deadline", func(t *testing.T) {
		f := newNotifyFake(1)
		db := &Database{server: f}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
		defer cancel()
		if e := db.WaitDisconnected(ctx); !errors.Is(e, context.DeadlineExceeded) {
			t.Fatal(e)
		}
	})
	t.Run("multiple_waiters_partial_disconnect", func(t *testing.T) {
		f := newNotifyFake(2)
		db := &Database{server: f}
		ch := make(chan error, 8)
		for range 8 {
			go func() { ch <- db.WaitDisconnected(context.Background()) }()
		}
		for range 8 {
			notifyRegistered(t, f)
		}
		f.set(1)
		for range 8 {
			notifyRegistered(t, f)
		}
		select {
		case e := <-ch:
			t.Fatalf("partial early success %v", e)
		default:
		}
		f.set(0)
		for range 8 {
			if e := notifyResult(t, ch); e != nil {
				t.Fatal(e)
			}
		}
	})
	t.Run("disconnect_before_select", func(t *testing.T) {
		f := newNotifyFake(1)
		f.afterSnapshot = func() { f.set(0) }
		db := &Database{server: f}
		ch := make(chan error, 1)
		go func() { ch <- db.WaitDisconnected(context.Background()) }()
		if e := notifyResult(t, ch); e != nil {
			t.Fatal(e)
		}
	})
	t.Run("close", func(t *testing.T) {
		f := newNotifyFake(1)
		db := &Database{server: f}
		ch := make(chan error, 1)
		go func() { ch <- db.WaitDisconnected(context.Background()) }()
		notifyRegistered(t, f)
		if e := db.Close(); e != nil {
			t.Fatal(e)
		}
		if e := notifyResult(t, ch); !errors.Is(e, ErrClosed) {
			t.Fatal(e)
		}
	})
	t.Run("failure_before_join", func(t *testing.T) {
		f := newNotifyFake(1)
		db := &Database{server: f}
		ch := make(chan error, 1)
		go func() { ch <- db.WaitDisconnected(context.Background()) }()
		notifyRegistered(t, f)
		want := errors.New("worker failed with owner retained")
		f.mu.Lock()
		f.cause = want
		close(f.failed)
		f.mu.Unlock()
		e := notifyResult(t, ch)
		if !errors.Is(e, ErrUnusable) || !errors.Is(e, want) {
			t.Fatal(e)
		}
		select {
		case <-f.done:
			t.Fatal("joined unexpectedly")
		default:
		}
	})
	t.Run("joined_exit", func(t *testing.T) {
		f := newNotifyFake(1)
		db := &Database{server: f}
		ch := make(chan error, 1)
		go func() { ch <- db.WaitDisconnected(context.Background()) }()
		notifyRegistered(t, f)
		f.mu.Lock()
		f.cause = errors.New("guest exited")
		close(f.done)
		f.mu.Unlock()
		if e := notifyResult(t, ch); !errors.Is(e, ErrUnusable) {
			t.Fatal(e)
		}
	})
}

// The wrapper deliberately hides DisconnectState to exercise the unchanged
// polling fallback. This selector is test-only; production has no mode switch.
type pollingBackend struct{ backend }

func BenchmarkDisconnectRetirementPoll(b *testing.B)   { benchmarkDisconnectRetirement(b, true) }
func BenchmarkDisconnectRetirementNotify(b *testing.B) { benchmarkDisconnectRetirement(b, false) }

// Measures pool.Close + WaitDisconnected on one reusable, healthy Pipe DB.
// Setup, SELECT, and final DB.Close are excluded. This is a narrow confirmation
// of connection retirement, not a Fork/batch/CPU or completed-disposal benchmark.
func benchmarkDisconnectRetirement(b *testing.B, polling bool) {
	b.StopTimer()
	ctx, cancel := context.WithTimeout(b.Context(), time.Minute)
	defer cancel()
	db, err := Start(ctx, Options{})
	if err != nil {
		b.Fatal(err)
	}
	defer func() {
		if err := db.Close(); err != nil {
			b.Fatal(err)
		}
	}()
	cfg, err := mysql.ParseDSN(db.DSN())
	if err != nil {
		b.Fatal(err)
	}
	cfg.DialFunc = db.DialContext
	connector, err := mysql.NewConnector(cfg)
	if err != nil {
		b.Fatal(err)
	}
	if polling {
		db.server = pollingBackend{db.server}
	}
	for i := 0; i < b.N; i++ {
		pool := sql.OpenDB(connector)
		var value int
		if err := pool.QueryRowContext(ctx, "SELECT 42").Scan(&value); err != nil || value != 42 {
			pool.Close()
			b.Fatalf("SELECT: value=%d err=%v", value, err)
		}
		b.StartTimer()
		err := pool.Close()
		if err == nil {
			err = db.WaitDisconnected(ctx)
		}
		b.StopTimer()
		if err != nil {
			b.Fatal(err)
		}
	}
}
