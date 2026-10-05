//go:build (darwin && arm64) || (linux && amd64)

// Anonymous linear-memory ownership. Only the execution owner releases it.
package base

import (
	"errors"
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"syscall"
)

type MemoryMapping struct {
	maximum uint64
	protect func([]byte, int) error
	unmap   func([]byte) error
	mu      sync.Mutex
	memory  []byte // Exact original mmap slice, required by syscall.Munmap.
	enabled uint64
}

var mappingActive, mappingReserved, mappingEnabled atomic.Uint64
var mappingCreates, mappingReleases, mappingReleaseFailures atomic.Uint64
var mappingGrowCalls, mappingGrowFailures, mappingPeakEnabled atomic.Uint64

// These are virtual/protection counters, not resident or committed physical RAM.
func MemoryMappingStats() map[string]uint64 {
	return map[string]uint64{
		"active_mappings": mappingActive.Load(), "active_reserved_bytes": mappingReserved.Load(),
		"active_rw_bytes": mappingEnabled.Load(), "creates": mappingCreates.Load(),
		"releases": mappingReleases.Load(), "release_failures": mappingReleaseFailures.Load(),
		"grow_calls": mappingGrowCalls.Load(), "grow_failures": mappingGrowFailures.Load(),
		"peak_total_rw_bytes": mappingPeakEnabled.Load(),
	}
}

func mappingRecordPeak() {
	n := mappingEnabled.Load()
	for p := mappingPeakEnabled.Load(); n > p; p = mappingPeakEnabled.Load() {
		if mappingPeakEnabled.CompareAndSwap(p, n) {
			break
		}
	}
}

func NewMemoryMapping(initial, maximum uint64) (*MemoryMapping, error) {
	return reserveMemoryMapping(initial, maximum, syscall.Mmap, syscall.Mprotect, syscall.Munmap)
}

// Per-owner syscall injection keeps failure-path tests deterministic and race safe.
func reserveMemoryMapping(initial, maximum uint64, mmap func(int, int64, int, int, int) ([]byte, error), protect func([]byte, int) error, unmap func([]byte) error) (*MemoryMapping, error) {
	if 65536%os.Getpagesize() != 0 || maximum == 0 || maximum > 1<<31 || initial > maximum || initial%65536 != 0 || maximum%65536 != 0 {
		return nil, fmt.Errorf("OS page size does not divide WASM page")
	}
	// Anonymous memory has a new zero-filled object. No file, CoW fixture,
	// MAP_FIXED, NORESERVE, POPULATE, custom pager, or guest-pointer rewrite.
	memory, err := mmap(-1, 0, int(maximum), syscall.PROT_NONE, syscall.MAP_PRIVATE|syscall.MAP_ANON)
	if err != nil {
		return nil, err
	}
	b := &MemoryMapping{memory: memory, maximum: maximum, protect: protect, unmap: unmap}
	mappingActive.Add(1)
	mappingReserved.Add(maximum)
	mappingCreates.Add(1)
	if err = b.Grow(0, initial); err != nil {
		return nil, errors.Join(err, b.Close())
	}
	return b, nil
}

// Called under the shared Module.MemMu, before MemSize.Store. Worker Module
// copies carry this same bound method; they never relocate or change headers.
func (b *MemoryMapping) Grow(old, next uint64) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	mappingGrowCalls.Add(1)
	if b.memory == nil || old != b.enabled || next < old || next > b.maximum || next%65536 != 0 {
		mappingGrowFailures.Add(1)
		return syscall.EINVAL
	}
	if next == old {
		return nil
	}
	if err := b.protect(b.memory[old:next], syscall.PROT_READ|syscall.PROT_WRITE); err != nil {
		mappingGrowFailures.Add(1)
		return err
	}
	// Never clear old/new pages in Go. Untouched anonymous pages are OS-zeroed.
	mappingEnabled.Add(next - old)
	b.enabled = next
	mappingRecordPeak()
	return nil
}

// Only the instance owner calls close, after ALL worker goroutines have joined.
// On unmap failure keep the slice and counters: do not claim successful release.
func (b *MemoryMapping) Close() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.memory == nil {
		return nil
	}
	if err := b.unmap(b.memory); err != nil {
		mappingReleaseFailures.Add(1)
		return &MemoryReleaseError{owner: b, cause: err}
	}
	mappingEnabled.Add(^(b.enabled - 1))
	mappingReserved.Add(^(b.maximum - 1))
	mappingActive.Add(^uint64(0))
	mappingReleases.Add(1)
	b.memory = nil
	b.enabled = 0
	return nil
}

// Bytes is the exact mapping slice. Do not resize, retain beyond Close, or use
// bytes outside the current logical range. It never contains Go pointers.
func (b *MemoryMapping) Bytes() []byte { return b.memory }

// MemoryReleaseError retains ownership when the OS refuses munmap. A caller may
// retry Close through errors.As; counters never report a failed release as done.
// No finalizer or unsafe forced reclamation is used.
type MemoryReleaseError struct {
	owner *MemoryMapping
	cause error
}

func (e *MemoryReleaseError) Error() string { return "linear memory release: " + e.cause.Error() }
func (e *MemoryReleaseError) Unwrap() error { return e.cause }
func (e *MemoryReleaseError) Close() error  { return e.owner.Close() }
