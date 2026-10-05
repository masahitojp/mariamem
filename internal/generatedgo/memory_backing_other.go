//go:build !((darwin && arm64) || (linux && amd64))

package generatedgo

import (
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Keep the previous allocation model outside the two supported platforms.
func newMemoryModule(h *host) (*base.Module, func() error, error) {
	return generated.NewWithWASI(h, nil, h), func() error { return nil }, nil
}
