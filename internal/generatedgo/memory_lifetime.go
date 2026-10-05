package generatedgo

import (
	"errors"
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
	*err = errors.Join(*err, release())
	runtime.KeepAlive(m)
}
