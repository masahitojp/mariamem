package generatedgo

import (
	"errors"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"runtime"
)

// Defer immediately after constructor ownership transfers. A non-cooperative
// worker keeps the mapping alive; forced reclamation is not supported.
func releaseMemoryModule(m *base.Module, release func() error, err *error) {
	base.SpikeWait(m)
	*err = errors.Join(*err, release())
	runtime.KeepAlive(m)
}
