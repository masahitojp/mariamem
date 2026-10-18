package artifacts

import (
	"context"
	"errors"
	"sync"

	"github.com/masahitojp/mariamem/internal/diagnostic"
)

// platformCheck retains only a successful supported-platform check. A failed
// caller does not poison later callers, and concurrent probes run one at a time.
// Each caller can attempt at most one probe; failed cohorts can probe up to N
// times for N callers, rather than retrying indefinitely within a call.
type platformCheck struct {
	mu       sync.Mutex
	ready    bool
	inFlight chan struct{}
	probe    func(context.Context) error
}

func platformContextError(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return diagnostic.Wrap("unsupported_platform", "platform", err)
	}
	return nil
}

func (c *platformCheck) validate(ctx context.Context) error {
	for {
		if err := platformContextError(ctx); err != nil {
			return err
		}
		c.mu.Lock()
		if c.ready {
			c.mu.Unlock()
			return platformContextError(ctx)
		}
		if done := c.inFlight; done != nil {
			c.mu.Unlock()
			select {
			case <-ctx.Done():
				return platformContextError(ctx)
			case <-done:
				continue
			}
		}
		done := make(chan struct{})
		c.inFlight = done
		c.mu.Unlock()
		return c.run(ctx, done)
	}
}

func (c *platformCheck) run(ctx context.Context, done chan struct{}) (err error) {
	success := false
	defer func() {
		// A panic must release waiters as well; it still propagates to its caller.
		c.mu.Lock()
		c.ready = success
		c.inFlight = nil
		close(done)
		c.mu.Unlock()
	}()
	if err = platformContextError(ctx); err != nil {
		return err
	}
	err = c.probe(ctx)
	if canceled := platformContextError(ctx); canceled != nil {
		// CommandContext can report a killed process instead of context.Canceled.
		// Preserve the command error and make the caller's cancellation observable.
		return errors.Join(err, canceled)
	}
	if err != nil {
		return err
	}
	success = true
	return nil
}
