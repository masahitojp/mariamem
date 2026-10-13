//go:build (darwin && arm64) || (linux && amd64)

package base

import "unsafe"

// These read exactly 1/2 bytes. Full fences surround the native load, with
// natural alignment and logical bounds checked by AtomicEA at the caller.
// ASM accesses are not Go race-detector instrumentation; detector silence does
// not certify synchronization or mmap safety. Keep the independent probes.
//go:noescape
func atomicRead8At(p unsafe.Pointer) uint32

//go:noescape
func atomicRead16At(p unsafe.Pointer) uint32
