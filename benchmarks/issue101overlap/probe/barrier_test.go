package probe

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestBarrierWaitsForAll(t *testing.T) {
	b := newBarrier(2)
	done := make(chan error, 1)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	go func() { done <- b.wait(ctx) }()
	select {
	case <-done:
		t.Fatal("barrier released early")
	case <-time.After(10 * time.Millisecond):
	}
	if err := b.wait(ctx); err != nil {
		t.Fatal(err)
	}
	if err := <-done; err != nil {
		t.Fatal(err)
	}
}
func TestBarrierCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if !errors.Is(newBarrier(2).wait(ctx), context.Canceled) {
		t.Fatal("cancellation lost")
	}
}
func TestForkFailuresStillJoinBothBarriers(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	r := &Report{Mode: "fork", origin: time.Now()}
	g := &waveGates{newBarrier(4), newBarrier(4)}
	expected := errors.New("injected fork failure")
	done := make(chan error, 4)
	sn := &Snapshot{Fork: func(context.Context) (*Database, error) { return nil, expected }}
	for i := 0; i < 4; i++ {
		go func(i int) { _, e := one(ctx, r, i, i, nil, sn, g); done <- e }(i)
	}
	for i := 0; i < 4; i++ {
		if e := <-done; !errors.Is(e, expected) || errors.Is(e, context.DeadlineExceeded) {
			t.Fatal(e)
		}
	}
}
