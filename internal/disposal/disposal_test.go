package disposal

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func deadline(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	t.Cleanup(cancel)
	return ctx
}

func TestLateCompletionOwnsDependentRemovalAndKeepsOriginalError(t *testing.T) {
	joined := make(chan struct{})
	var joinOnce sync.Once
	t.Cleanup(func() { joinOnce.Do(func() { close(joined) }) })
	cause := errors.New("startup failed")
	owner := New(func(ctx context.Context) error { return Wait(ctx, joined) })
	err := Retain(cause, errors.New("join timed out"), owner)
	path := filepath.Join(t.TempDir(), "transfer")
	if e := os.Mkdir(path, 0700); e != nil {
		t.Fatal(e)
	}
	err = RemoveAfter(fmt.Errorf("guest_ready: %w", err), path)
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		t.Fatal("internal probe changed original failure into caller timeout", err)
	}
	parents := Owners(err)
	if len(parents) != 1 {
		t.Fatal("not a single dependent owner")
	}
	if _, e := os.Stat(path); e != nil {
		t.Fatal("removed before join", e)
	}
	if owner.Complete() || parents[0].Complete() {
		t.Fatal("premature disposal")
	}
	probe, cancel := context.WithCancel(context.Background())
	cancel()
	if e := Retry(probe, err); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
	joinOnce.Do(func() { close(joined) })
	ctx := deadline(t)
	if e := Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if _, e := os.Stat(path); !os.IsNotExist(e) {
		t.Fatal("late transfer retained", e)
	}
	if !errors.Is(err, cause) {
		t.Fatal("cleanup converted startup failure into success")
	}
	if e := Retry(ctx, err); e != nil {
		t.Fatal("duplicate cleanup", e)
	}
}

func TestRemovalFailureRetainsRetryOwnerAndOriginalCause(t *testing.T) {
	cause, denied := errors.New("capture failed"), errors.New("remove denied")
	var allow atomic.Bool
	var calls atomic.Int32
	err := After(cause, func() error {
		calls.Add(1)
		if !allow.Load() {
			return denied
		}
		return nil
	})
	if !errors.Is(err, cause) || !errors.Is(err, denied) {
		t.Fatal(err)
	}
	owners := Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost failed removal")
	}
	allow.Store(true)
	ctx := deadline(t)
	if e := Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	n := calls.Load()
	if e := Retry(ctx, err); e != nil || calls.Load() != n {
		t.Fatal("repeated successful disposal", e)
	}
	if !errors.Is(err, cause) || !errors.Is(err, denied) {
		t.Fatal("historical failure was rewritten")
	}
}

func TestConcurrentRetryAndWaiterCancellation(t *testing.T) {
	entered, joined := make(chan struct{}), make(chan struct{})
	var calls atomic.Int32
	var release sync.Once
	t.Cleanup(func() { release.Do(func() { close(joined) }) })
	owner := New(func(ctx context.Context) error {
		if calls.Add(1) == 1 {
			close(entered)
		}
		return Wait(ctx, joined)
	})
	ctx := deadline(t)
	done := make(chan error, 8)
	go func() { done <- owner.Retry(ctx) }()
	select {
	case <-entered:
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	probe, cancel := context.WithCancel(context.Background())
	cancel()
	if err := owner.Retry(probe); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	for range 7 {
		go func() { done <- owner.Retry(ctx) }()
	}
	release.Do(func() { close(joined) })
	for range 8 {
		select {
		case err := <-done:
			if err != nil {
				t.Fatal(err)
			}
		case <-ctx.Done():
			t.Fatal(ctx.Err())
		}
	}
	if calls.Load() != 1 || !owner.Complete() {
		t.Fatal("cleanup not serialized", calls.Load())
	}
}

func TestJoinedCleanupDistinguishesOperationAndCleanupResult(t *testing.T) {
	cause := errors.New("operation failed but disposed")
	var calls int
	if e := After(cause, func() error { calls++; return nil }); e != cause {
		t.Fatal(e)
	}
	if e := CleanupAfter(cause, func() error { calls++; return nil }); e != nil {
		t.Fatal(e)
	}
	if calls != 2 {
		t.Fatal(calls)
	}
	joined := make(chan struct{})
	close(joined)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if e := Wait(ctx, joined); e != nil {
		t.Fatal("ignored known completion", e)
	}
}

func TestJoinedErrorsRetainIndependentOwnersOnce(t *testing.T) {
	a := New(func(context.Context) error { return nil })
	b := New(func(context.Context) error { return nil })
	x := Retain(errors.New("a"), errors.New("a cleanup"), a)
	y := Retain(errors.New("b"), errors.New("b cleanup"), b)
	err := fmt.Errorf("outer: %w", errors.Join(x, y, x))
	if len(Owners(err)) != 2 {
		t.Fatal("lost owner or duplicate")
	}
	if e := Retry(deadline(t), err); e != nil {
		t.Fatal(e)
	}
}
