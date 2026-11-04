package forklimit

import (
	"encoding/binary"
	"syscall"
)

func memoryLimits() []uint64 {
	// Sysctl returns raw bytes; hw.memsize is an unsigned 64-bit value.
	raw, err := syscall.Sysctl("hw.memsize")
	if err != nil {
		return nil
	}
	// syscall.Sysctl strips one trailing NUL even for a binary value.
	b := []byte(raw)
	if len(b) == 7 {
		b = append(b, 0)
	}
	if len(b) != 8 {
		return nil
	}
	return []uint64{binary.NativeEndian.Uint64(b)}
}
