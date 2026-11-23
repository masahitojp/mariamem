//go:build !windows

package base

import "syscall"

func mapPreparedMemory(fd, size int, readOnly bool) ([]byte, error) {
	prot := syscall.PROT_READ
	if !readOnly {
		prot |= syscall.PROT_WRITE
	}
	return syscall.Mmap(fd, 0, size, prot, syscall.MAP_PRIVATE)
}
func unmapPreparedMemory(data []byte) error { return syscall.Munmap(data) }
