package generatedgo

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/disposal"
	"runtime"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Register immediately after constructor ownership transfers. WaitThreads
// returns a retained panic; using SpikeWait here would skip unmap on a trap.
// A non-cooperative agent keeps ownership alive instead of being forcibly freed.
func releaseMemoryModule(m *base.Module, release func() error, err *error) {
	if p := m.Threads.WaitThreads(); p != nil && *err == nil {
		*err = guestFailure(p)
	}
	*err = errors.Join(*err, retainRelease(release))
	runtime.KeepAlive(m)
}

// Retain retryable resources separately from the original execution result.
// The owner serializes retries and is complete only after actual release.
func retainRelease(release func() error) error {
	if err := release(); err != nil {
		owner := disposal.New(func(context.Context) error { return release() })
		return disposal.Retain(nil, err, owner)
	}
	return nil
}

// A generic descriptor Close error does not prove that retrying is safe.
// Retain the owner and its resources without repeating Close on a possibly
// already-reused native descriptor. Explicit recovery needs a typed contract.
func closeDescriptors(w *base.WasiStubs) error {
	if err := w.CloseDescriptors(); err != nil {
		owner := disposal.New(func(context.Context) error { runtime.KeepAlive(w); return err })
		return disposal.Retain(nil, err, owner)
	}
	return nil
}
