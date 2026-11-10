package probe

import (
	"context"
	"sync/atomic"
)

type barrier struct {
	remaining atomic.Int32
	done      chan struct{}
}

func newBarrier(n int) *barrier {
	b := &barrier{done: make(chan struct{})}
	b.remaining.Store(int32(n))
	return b
}
func (b *barrier) wait(ctx context.Context) error {
	if b.remaining.Add(-1) == 0 {
		close(b.done)
	}
	select {
	case <-b.done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

type waveGates struct{ fork, sql *barrier }
