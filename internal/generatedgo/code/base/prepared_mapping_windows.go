package base

import (
	"sync"
	"syscall"
	"unsafe"
)

var preparedMappingOwners = struct {
	sync.Mutex
	views map[uintptr]int
}{views: make(map[uintptr]int)}

func mapPreparedMemory(fd, size int, readOnly bool) ([]byte, error) {
	protection, access := uint32(syscall.PAGE_WRITECOPY), uint32(syscall.FILE_MAP_COPY)
	if readOnly {
		protection, access = syscall.PAGE_READONLY, syscall.FILE_MAP_READ
	}
	mapping, err := syscall.CreateFileMapping(syscall.Handle(fd), nil, protection, 0, 0, nil)
	if err != nil {
		return nil, err
	}
	defer syscall.CloseHandle(mapping)
	address, err := syscall.MapViewOfFile(mapping, access, 0, 0, uintptr(size))
	if err != nil {
		return nil, err
	}
	preparedMappingOwners.Lock()
	preparedMappingOwners.views[address] = size
	preparedMappingOwners.Unlock()
	return unsafe.Slice((*byte)(unsafe.Pointer(address)), size), nil
}
func unmapPreparedMemory(data []byte) error {
	if len(data) == 0 {
		return nil
	}
	address := uintptr(unsafe.Pointer(&data[0]))
	preparedMappingOwners.Lock()
	defer preparedMappingOwners.Unlock()
	if size, ok := preparedMappingOwners.views[address]; !ok || size != len(data) {
		return syscall.EINVAL
	}
	if err := syscall.UnmapViewOfFile(address); err != nil {
		return err
	}
	delete(preparedMappingOwners.views, address)
	return nil
}
