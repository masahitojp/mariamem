package mariamem

import (
	"context"
	"github.com/masahitojp/mariamem/internal/disposal"
	"sync"
)

// An operation result ends an attempt; disposal success is a separate fact.
// No exported API is added. The stopped boundary is supplied by #205's backend.
type closeOperation struct {
	stopped chan struct{}
	done    chan struct{}
	once    sync.Once
	stopErr error // published by closing stopped
	err     error // published by closing done
	confirm func() bool
}

func newCloseOperation() *closeOperation {
	return &closeOperation{stopped: make(chan struct{}), done: make(chan struct{})}
}
func (o *closeOperation) notifyStopped(err error) {
	o.once.Do(func() { o.stopErr = err; close(o.stopped) })
}
func (o *closeOperation) Wait(ctx context.Context) error {
	if err := disposal.Wait(ctx, o.done); err != nil {
		return err
	}
	return o.err
}

// A failed attempt may be reclaimed later without rewriting its saved error.
func (o *closeOperation) Disposed() bool {
	select {
	case <-o.done:
	default:
		return false
	}
	return !cleanupPending(o.err) && o.confirm != nil && o.confirm()
}
