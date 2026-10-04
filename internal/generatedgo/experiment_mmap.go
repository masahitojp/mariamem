//go:build experiment_mmap && ((darwin && arm64) || (linux && amd64))

// Disposable spike, not a production backing implementation.
package generatedgo

import (
	"errors"
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"syscall"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

const experimentMaximum = 2 << 30

type experimentMapping struct {
	mu      sync.Mutex
	memory  []byte // Exact original mmap slice, required by syscall.Munmap.
	enabled uint64
}

var experimentActive, experimentReserved, experimentEnabled atomic.Uint64
var experimentCreates, experimentReleases, experimentReleaseFailures atomic.Uint64
var experimentGrowCalls, experimentGrowFailures, experimentPeakEnabled atomic.Uint64

// These are virtual/protection counters, not resident or committed physical RAM.
func ExperimentMappingStats() map[string]uint64 {
	return map[string]uint64{
		"active_mappings": experimentActive.Load(), "active_reserved_bytes": experimentReserved.Load(),
		"active_rw_bytes": experimentEnabled.Load(), "creates": experimentCreates.Load(),
		"releases": experimentReleases.Load(), "release_failures": experimentReleaseFailures.Load(),
		"grow_calls": experimentGrowCalls.Load(), "grow_failures": experimentGrowFailures.Load(),
		"peak_total_rw_bytes": experimentPeakEnabled.Load(),
	}
}

func experimentRecordPeak() {
	n := experimentEnabled.Load()
	for p := experimentPeakEnabled.Load(); n > p; p = experimentPeakEnabled.Load() {
		if experimentPeakEnabled.CompareAndSwap(p, n) {
			break
		}
	}
}

func experimentReserve() (*experimentMapping, error) {
	if 65536%os.Getpagesize() != 0 {
		return nil, fmt.Errorf("OS page size does not divide WASM page")
	}
	// Anonymous memory has a new zero-filled object. No file, CoW fixture,
	// MAP_FIXED, NORESERVE, POPULATE, custom pager, or guest-pointer rewrite.
	memory, err := syscall.Mmap(-1, 0, experimentMaximum, syscall.PROT_NONE, syscall.MAP_PRIVATE|syscall.MAP_ANON)
	if err != nil {
		return nil, err
	}
	b := &experimentMapping{memory: memory}
	experimentActive.Add(1)
	experimentReserved.Add(experimentMaximum)
	experimentCreates.Add(1)
	if err = b.enable(0, generated.InitialMemoryBytes); err != nil {
		return nil, errors.Join(err, b.close())
	}
	return b, nil
}

// Called under the shared Module.MemMu, before MemSize.Store. Worker Module
// copies carry this same bound method; they never relocate or change headers.
func (b *experimentMapping) enable(old, next uint64) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	experimentGrowCalls.Add(1)
	if b.memory == nil || old != b.enabled || next < old || next > experimentMaximum || next%65536 != 0 {
		experimentGrowFailures.Add(1)
		return syscall.EINVAL
	}
	if next == old {
		return nil
	}
	if err := syscall.Mprotect(b.memory[old:next], syscall.PROT_READ|syscall.PROT_WRITE); err != nil {
		experimentGrowFailures.Add(1)
		return err
	}
	// Never clear old/new pages in Go. Untouched anonymous pages are OS-zeroed.
	experimentEnabled.Add(next - old)
	b.enabled = next
	experimentRecordPeak()
	return nil
}

// Only the instance owner calls close, after ALL worker goroutines have joined.
// On unmap failure keep the slice and counters: do not claim successful release.
func (b *experimentMapping) close() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.memory == nil {
		return nil
	}
	if err := syscall.Munmap(b.memory); err != nil {
		experimentReleaseFailures.Add(1)
		return err
	}
	experimentEnabled.Add(^(b.enabled - 1))
	experimentReserved.Add(^(uint64(experimentMaximum) - 1))
	experimentActive.Add(^uint64(0))
	experimentReleases.Add(1)
	b.memory = nil
	b.enabled = 0
	return nil
}

func experimentMappedModule(h *host) (m *base.Module, release func() error, err error) {
	b, err := experimentReserve()
	if err != nil {
		return nil, nil, err
	}
	transferred := false
	defer func() {
		if !transferred {
			err = errors.Join(err, b.close())
		}
	}()
	// The unchanged generated constructor initializes the released data/globals.
	// Full slice length keeps MaxMem at 2 GiB while MemSize starts at 256 MiB.
	m = generated.NewWithMemory(h, nil, h, b.memory, generated.InitialMemoryBytes)
	m.ExperimentMemoryCommit = b.enable
	transferred = true
	return m, b.close, nil
}
