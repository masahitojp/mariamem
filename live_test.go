package mariamem

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	endpoint "github.com/masahitojp/mariamem/internal/live"
)

func TestClosedSnapshotLivePreservesErrorIdentity(t *testing.T) {
	s := &Snapshot{closed: true, opts: Options{ShutdownTimeout: time.Second}}
	live, err := s.Live(context.Background())
	if live != nil || !errors.Is(err, ErrClosed) {
		t.Fatal(live, err)
	}
	var detail *HostError
	if !errors.As(err, &detail) || detail.Closed || detail.Stage != "live_precondition" {
		t.Fatal(err)
	}
}
func TestLivePublicMappingMetadataAndClose(t *testing.T) {
	fake := &fakeBackend{}
	db := testDB(t, fake)
	e, err := endpoint.New(context.Background(), endpoint.Factory{Check: func() error { return nil }, Start: func(context.Context) (endpoint.Child, error) { return liveChild{db}, nil }}, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	l := &Live{endpoint: e, info: ConnectionInfo{Host: "127.0.0.1", Port: e.Port(), User: "root", Database: "test"}}
	defer l.Close()
	info := l.ConnectionInfo()
	if info.Port == 0 || l.DSN() == "" {
		t.Fatal(info)
	}
	if err := l.Reset(context.Background(), ResetOptions{DrainTimeout: -1}); err == nil {
		t.Fatal("invalid timeout accepted")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := l.Reset(ctx, ResetOptions{}); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	if l.Status().State != "ready" || l.Status().Generation != 0 {
		t.Fatal(l.Status())
	}
	if err := l.Close(); err != nil {
		t.Fatal(err)
	}
	if err := l.Close(); err != nil {
		t.Fatal(err)
	}
	if fake.closes != 1 || l.ConnectionInfo() != info || l.Status().State != "closed" {
		t.Fatal(fake.closes, l.Status())
	}
	if err := l.Reset(context.Background(), ResetOptions{}); !errors.Is(err, ErrClosed) {
		t.Fatal(err)
	}
	busy := liveError(diagnostic.Wrap("busy", "live_drain", errors.New("held idle session")), false)
	if !errors.Is(busy, ErrBusy) {
		t.Fatal(busy)
	}
}

func TestLiveAdapterRetirementRetry(t *testing.T) {
	failure := errors.New("backend shutdown failed")
	oldBackend := &fakeBackend{closeErr: failure}
	old := testDB(t, oldBackend)
	children := []*Database{old, testDB(t, &fakeBackend{}), testDB(t, &fakeBackend{})}
	next := 0
	e, err := endpoint.New(context.Background(), endpoint.Factory{Check: func() error { return nil }, Start: func(context.Context) (endpoint.Child, error) {
		child := children[next]
		next++
		return liveChild{child}, nil
	}}, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if s := e.Status(); s.State != "failed" || s.Generation != 0 {
		t.Fatal(s)
	}
	oldBackend.closeErr = nil
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	if s := e.Status(); s.State != "ready" || s.Generation != 1 {
		t.Fatal(s)
	}
	if oldBackend.closes != 2 {
		t.Fatal(oldBackend.closes)
	}
	if err := old.Close(); !errors.Is(err, failure) || oldBackend.closes != 2 {
		t.Fatal(err, oldBackend.closes)
	}
}

func TestLiveAdapterRepeatedCloseRetriesDisposal(t *testing.T) {
	failure := errors.New("backend shutdown failed")
	backend := &fakeBackend{closeErr: failure}
	db := testDB(t, backend)
	e, err := endpoint.New(context.Background(), endpoint.Factory{Check: func() error { return nil }, Start: func(context.Context) (endpoint.Child, error) { return liveChild{db}, nil }}, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	first := e.Close()
	if !errors.Is(first, failure) {
		t.Fatal(first)
	}
	backend.closeErr = nil
	if second := e.Close(); second != first || backend.closes != 2 {
		t.Fatal(second, backend.closes)
	}
	if third := e.Close(); third != first || backend.closes != 2 {
		t.Fatal(third, backend.closes)
	}
	if err := db.Close(); !errors.Is(err, failure) {
		t.Fatal(err)
	}
}
