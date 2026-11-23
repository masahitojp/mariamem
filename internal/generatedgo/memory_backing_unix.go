//go:build (darwin && arm64) || (linux && (amd64 || arm64))

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
