//go:build (darwin && arm64) || (linux && amd64) || (windows && (amd64 || arm64))

// Anonymous linear-memory ownership. Only the execution owner releases it.
package base

import (
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
	if err := b.protect(b.memory[old:next], mappingReadWrite); err != nil {
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
