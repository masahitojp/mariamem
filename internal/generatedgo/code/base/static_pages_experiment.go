//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"errors"
	"os"
	"runtime"
	"syscall"
	"unsafe"
)

// ImageRange is a page-aligned initialized range. Experiment only.
type ImageRange struct {
	Offset uint64 `json:"offset"`
	Length uint64 `json:"length"`
}

// NewStaticPageMapping overlays only initialized pages on an owned anonymous
// reservation. Every overlay is private; all other pages remain anonymous.
func NewStaticPageMapping(fd int, initial, maximum uint64, ranges []ImageRange) (*MemoryMapping, error) {
	return newStaticPageMapping(fd, initial, maximum, ranges, replaceImagePages, syscall.Munmap)
}
func replaceImagePages(addr, length uintptr, fd int, offset uint64) error {
	r, _, e := syscall.Syscall6(syscall.SYS_MMAP, addr, length, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_FIXED|syscall.MAP_PRIVATE, uintptr(fd), uintptr(offset))
	if e != 0 {
		return e
	}
	if r != addr {
		panic("MAP_FIXED returned a different address")
	}
	return nil
}
func newStaticPageMapping(fd int, initial, maximum uint64, ranges []ImageRange, replace func(uintptr, uintptr, int, uint64) error, unmap func([]byte) error) (*MemoryMapping, error) {
	var st syscall.Stat_t
	if err := syscall.Fstat(fd, &st); err != nil {
		return nil, err
	}
	if st.Size != int64(maximum) {
		return nil, syscall.EINVAL
	}
	page := uint64(os.Getpagesize())
	end := uint64(0)
	for _, r := range ranges {
		if r.Length == 0 || r.Offset%page != 0 || r.Length%page != 0 || r.Offset < end || r.Offset > initial || r.Length > initial-r.Offset {
			return nil, syscall.EINVAL
		}
		end = r.Offset + r.Length
	}
	b, err := reserveMemoryMapping(initial, maximum, syscall.Mmap, syscall.Mprotect, unmap)
	if err != nil {
		return nil, err
	}
	// MAP_FIXED is confined to this not-yet-published, fully owned reservation.
	// Keep the exact original mmap slice for one final Munmap over all segments.
	for _, r := range ranges {
		err = replace(uintptr(unsafe.Pointer(&b.memory[r.Offset])), uintptr(r.Length), fd, r.Offset)
		runtime.KeepAlive(b)
		if err != nil {
			return nil, errors.Join(err, b.Close())
		} // typed debt survives failed cleanup
	}
	return b, nil
}
