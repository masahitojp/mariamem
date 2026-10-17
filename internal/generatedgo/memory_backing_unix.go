//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"context"
	"errors"
	"fmt"
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/timing"
)

// Constructor ownership transfers only after all generated initialization succeeds.
func newMemoryModule(h *host) (m *base.Module, release func() error, err error) {
	return initializeMemoryModule(func() (*base.MemoryMapping, error) { return base.NewMemoryMapping(generated.InitialMemoryBytes, 2<<30) }, func(b *base.MemoryMapping) *base.Module {
		m := generated.NewWithMemory(h, nil, h, b.Bytes(), generated.InitialMemoryBytes)
		installGuestThreadLifetime(m)
		return m
	})
}
func initializeMemoryModule(reserve func() (*base.MemoryMapping, error), initialize func(*base.MemoryMapping) *base.Module) (m *base.Module, release func() error, err error) {
	ctx, finishTiming := timing.Begin(context.Background(), "memory_init")
	defer finishTiming()
	b, err := reserve()
	timing.Mark(ctx, "mapping_reserved")
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
	timing.Mark(ctx, "generated_initialized")
	m.PrepareMemoryGrow = b.Grow
	transferred = true
	return m, b.Close, nil
}
