//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"errors"
	"sync"
	"syscall"
	"testing"
)

func TestMappingFailureOwnership(t *testing.T) {
	before := MemoryMappingStats()
	var unmapped int
	_, err := reserveMemoryMapping(65536, 3*65536, syscall.Mmap, func([]byte, int) error { return syscall.ENOMEM }, func(b []byte) error { unmapped++; return syscall.Munmap(b) })
	if !errors.Is(err, syscall.ENOMEM) || unmapped != 1 || MemoryMappingStats()["active_mappings"] != before["active_mappings"] {
		t.Fatal("initial protect failure", err, unmapped)
	}
	_, err = reserveMemoryMapping(65536, 3*65536, func(int, int64, int, int, int) ([]byte, error) { return nil, syscall.ENOMEM }, syscall.Mprotect, syscall.Munmap)
	if !errors.Is(err, syscall.ENOMEM) || MemoryMappingStats()["creates"] != before["creates"]+1 {
		t.Fatal("reserve failure", err)
	}
	b, err := NewMemoryMapping(65536, 3*65536)
	if err != nil {
		t.Fatal(err)
	}
	b.memory[31] = 77
	ptr := &b.memory[0]
	protect := b.protect
	b.protect = func([]byte, int) error { return syscall.ENOMEM }
	if err = b.Grow(65536, 2*65536); !errors.Is(err, syscall.ENOMEM) || b.enabled != 65536 || b.memory[31] != 77 {
		t.Fatal("grow failed state", err)
	}
	b.protect = protect
	if err = b.Grow(65536, 2*65536); err != nil || &b.memory[0] != ptr || b.memory[65536] != 0 {
		t.Fatal("grow contract", err)
	}
	if err = b.Grow(2*65536, 4*65536); !errors.Is(err, syscall.EINVAL) || b.enabled != 2*65536 {
		t.Fatal("max state", err)
	}
	unmap := b.unmap
	b.unmap = func([]byte) error { return syscall.EBUSY }
	if err = b.Close(); !errors.Is(err, syscall.EBUSY) || b.memory == nil {
		t.Fatal("false release", err)
	}
	b.unmap = unmap
	var wg sync.WaitGroup
	errs := make(chan error, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); errs <- b.Close() }()
	}
	wg.Wait()
	close(errs)
	for e := range errs {
		if e != nil {
			t.Fatal(e)
		}
	}
	if MemoryMappingStats()["active_mappings"] != before["active_mappings"] || MemoryMappingStats()["releases"] != before["releases"]+2 {
		t.Fatal("exactly once release", MemoryMappingStats())
	}
}

func TestMappingInitialCleanupFailureRetainsOwner(t *testing.T) {
	before := MemoryMappingStats()
	var saved []byte
	_, err := reserveMemoryMapping(65536, 3*65536, syscall.Mmap,
		func([]byte, int) error { return syscall.ENOMEM },
		func(b []byte) error { saved = b; return syscall.EBUSY })
	var owned *MemoryReleaseError
	if !errors.Is(err, syscall.ENOMEM) || !errors.Is(err, syscall.EBUSY) || !errors.As(err, &owned) || owned.owner.memory == nil || len(saved) != 3*65536 {
		t.Fatal("lost failed-init mapping owner", err)
	}
	owned.owner.unmap = syscall.Munmap
	if err := owned.Close(); err != nil {
		t.Fatal(err)
	}
	if err := owned.Close(); err != nil {
		t.Fatal(err)
	}
	after := MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"] != before["releases"]+1 {
		t.Fatal("retry did not release exactly once", before, after)
	}
}
