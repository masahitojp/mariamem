package probe

import (
	"context"
	"database/sql"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestRendezvousCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	g := newRendezvous(4, nil)
	result := make(chan error, 1)
	go func() { result <- g.wait(ctx) }()
	cancel()
	select {
	case e := <-result:
		if !errors.Is(e, context.Canceled) {
			t.Fatal(e)
		}
	case <-time.After(time.Second):
		t.Fatal("blocked cancellation")
	}
}
func TestFixedWaveForkFailureJoinsChildren(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	var attempts, completed, closes atomic.Int32
	sn := &Snapshot{Fork: func(peerCtx context.Context) (*Database, error) {
		n := attempts.Add(1)
		defer completed.Add(1)
		if n == 1 {
			return nil, errors.New("injected fork failure")
		}
		return &Database{Open: func(string) (*sql.DB, error) {
			if completed.Load() != 4 {
				t.Error("connection admitted before all Forks returned")
			}
			return nil, errors.New("injected connect failure")
		}, Close: func() error {
			if peerCtx.Err() != nil {
				t.Error("peer canceled before disposal")
			}
			closes.Add(1)
			return nil
		}}, nil
	}}
	r := &Report{Parallel: 4, Count: 48, origin: time.Now()}
	e := fixedWaveBatch(ctx, r, nil, sn, cancel)
	if e == nil || attempts.Load() != 4 || len(r.Samples) != 4 || len(r.Waves) != 1 || closes.Load() != 3 {
		t.Fatalf("failure did not join first wave: %v attempts=%d samples=%d", e, attempts.Load(), len(r.Samples))
	}
	for _, s := range r.Samples {
		if !s.Cleanup {
			t.Fatal("cleanup")
		}
	}
}
func TestRendezvousReleasesOnlyAfterAllArrive(t *testing.T) {
	var callback atomic.Int32
	g := newRendezvous(4, func() { callback.Add(1) })
	var wg sync.WaitGroup
	passed := make(chan struct{}, 4)
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if e := g.wait(context.Background()); e != nil {
				t.Error(e)
			}
			passed <- struct{}{}
		}()
	}
	deadline := time.Now().Add(time.Second)
	for g.count.Load() != 3 {
		if time.Now().After(deadline) {
			t.Fatal("did not arrive")
		}
		time.Sleep(time.Millisecond)
	}
	select {
	case <-passed:
		t.Fatal("released before fourth arrival")
	default:
	}
	if e := g.wait(context.Background()); e != nil {
		t.Fatal(e)
	}
	wg.Wait()
	if callback.Load() != 1 || len(passed) != 3 {
		t.Fatal("release/callback count")
	}
}
