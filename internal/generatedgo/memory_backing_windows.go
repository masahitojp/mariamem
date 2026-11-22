//go:build windows && (amd64 || arm64)

package generatedgo

import (
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Windows initializes each private VirtualAlloc reservation directly.
func newMemoryModule(h *host) (*base.Module, func() error, error) {
	return initializeMemoryModule(func() (*base.MemoryMapping, error) {
		return base.NewMemoryMapping(generated.InitialMemoryBytes, 2<<30)
	}, func(b *base.MemoryMapping) *base.Module {
		m := generated.NewWithMemory(h, nil, h, b.Bytes(), generated.InitialMemoryBytes)
		installGuestThreadLifetime(m)
		return m
	})
}
