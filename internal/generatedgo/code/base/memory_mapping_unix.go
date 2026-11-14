//go:build (darwin && arm64) || (linux && (amd64 || arm64))

package base

import (
	"errors"
	"fmt"
	"os"
	"syscall"
)

const mappingReadWrite = syscall.PROT_READ | syscall.PROT_WRITE

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
