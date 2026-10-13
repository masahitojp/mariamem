//go:build !((darwin && arm64) || (linux && amd64))

package generatedgo

import (
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Keep the previous allocation model outside the two supported platforms.
func newMemoryModule(h *host) (*base.Module, func() error, error) {
	m := generated.NewWithWASI(h, nil, h)
	installGuestThreadLifetime(m)
	return m, func() error { return nil }, nil
}
