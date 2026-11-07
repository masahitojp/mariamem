package base

import (
	"hash/crc32"
	"runtime"
	"unsafe"
)

var crc32cTable = crc32.MakeTable(crc32.Castagnoli)

// CRC32C computes the pinned guest's full-page Castagnoli checksum. The caller
// retains the stored-checksum and LSN comparisons; this never caches a result.
// The borrowed bytes have the same lifetime as the caller's guest page access.
func CRC32C(m *Module, addr, size int32) uint32 {
	start := MemoryEA(m, uint64(uint32(addr)), 0, uint64(uint32(size)))
	b := unsafe.Slice((*byte)(unsafe.Add(m.M, uintptr(start))), int(uint32(size)))
	value := crc32.Checksum(b, crc32cTable)
	runtime.KeepAlive(m)
	return value
}
