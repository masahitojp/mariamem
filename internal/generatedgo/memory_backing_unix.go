//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/image"
)

// Constructor ownership transfers only after all generated initialization succeeds.
func newMemoryModule(h *host) (m *base.Module, release func() error, err error) {
	m, release, err = image.Acquire(h, h)
	if err != nil {
		return nil, nil, err
	}
	defer func() {
		if p := recover(); p != nil {
			panic(errors.Join(fmt.Errorf("generated memory initialization: %v", p), release()))
		}
	}()
	installGuestThreadLifetime(m)
	return m, release, nil
}
func initializeMemoryModule(reserve func() (*base.MemoryMapping, error), initialize func(*base.MemoryMapping) *base.Module) (m *base.Module, release func() error, err error) {
	b, err := reserve()
	if err != nil {
		return nil, nil, err
	}
	transferred := false
	defer func() {
		if !transferred {
			closeErr := b.Close()
			if p := recover(); p != nil {
				panic(errors.Join(fmt.Errorf("generated memory initialization: %v", p), closeErr))
			}
			err = errors.Join(err, closeErr)
		}
	}()
	m = initialize(b)
	m.PrepareMemoryGrow = b.Grow
	transferred = true
	return m, b.Close, nil
}
