//go:build windows && (amd64 || arm64)

package base

import (
	"errors"
	"fmt"
	"os"
	"syscall"
	"unsafe"
)

var memoryKernel = syscall.NewLazyDLL("kernel32.dll")
var memoryAlloc = memoryKernel.NewProc("VirtualAlloc")
var memoryFree = memoryKernel.NewProc("VirtualFree")

const mappingReadWrite = 4 // PAGE_READWRITE

func NewMemoryMapping(initial, maximum uint64) (*MemoryMapping, error) {
	if os.Getpagesize() <= 0 || 65536%os.Getpagesize() != 0 || maximum == 0 || maximum > 1<<31 || initial > maximum || initial%65536 != 0 || maximum%65536 != 0 {
		return nil, fmt.Errorf("OS page size does not divide WASM page")
	}
	address, _, err := memoryAlloc.Call(0, uintptr(maximum), 0x2000, 1) // MEM_RESERVE, PAGE_NOACCESS
	if address == 0 {
		return nil, err
	}
	memory := unsafe.Slice((*byte)(unsafe.Pointer(address)), int(maximum))
	b := &MemoryMapping{memory: memory, maximum: maximum,
		protect: func(p []byte, protection int) error {
			if len(p) == 0 {
				return nil
			}
			addr := uintptr(unsafe.Pointer(&p[0]))
			got, _, e := memoryAlloc.Call(addr, uintptr(len(p)), 0x1000, uintptr(protection)) // MEM_COMMIT
			if got == 0 {
				return e
			}
			if got != addr {
				return errors.New("linear memory commit moved address")
			}
			return nil
		},
		unmap: func(p []byte) error {
			ok, _, e := memoryFree.Call(uintptr(unsafe.Pointer(&p[0])), 0, 0x8000) // MEM_RELEASE
			if ok == 0 {
				return e
			}
			return nil
		},
	}
	mappingActive.Add(1)
	mappingReserved.Add(maximum)
	mappingCreates.Add(1)
	if err := b.Grow(0, initial); err != nil {
		return nil, errors.Join(err, b.Close())
	}
	return b, nil
}
