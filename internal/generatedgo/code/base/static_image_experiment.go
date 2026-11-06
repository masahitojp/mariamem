//go:build (darwin && arm64) || (linux && amd64)

package base

import "syscall"

// Experiment only: retain the existing owner, Grow, counters and Close logic.
// The immutable backing FD must cover maximum bytes. It remains caller-owned.
func NewStaticImageMapping(fd int, initial, maximum uint64) (*MemoryMapping, error) {
	return newStaticImageMapping(fd, initial, maximum, syscall.Mmap, syscall.Mprotect, syscall.Munmap)
}

func newStaticImageMapping(fd int, initial, maximum uint64, mmap func(int, int64, int, int, int) ([]byte, error), protect func([]byte, int) error, unmap func([]byte) error) (*MemoryMapping, error) {
	var st syscall.Stat_t
	if err := syscall.Fstat(fd, &st); err != nil {
		return nil, err
	}
	if st.Size != int64(maximum) {
		return nil, syscall.EINVAL
	}
	return reserveMemoryMapping(initial, maximum,
		func(_ int, off int64, n, prot, flags int) ([]byte, error) {
			return mmap(fd, off, n, prot, syscall.MAP_PRIVATE)
		}, protect, unmap)
}
