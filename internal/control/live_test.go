package control

import (
	"context"
	"encoding/json"
	"errors"
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
	if len(caps) != 1 || caps[0] != "live-v1" {
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
