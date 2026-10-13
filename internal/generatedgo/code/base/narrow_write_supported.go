//go:build (darwin && arm64) || (linux && amd64)

package base

import "unsafe"

// Exact 1/2-byte memory operands, with conservative sequential consistency.
// AtomicEA checks logical bounds/alignment before callers reach these methods.
// Assembly synchronization is invisible to Go's race detector, including heap
// backing. Do not infer safety of ordinary overlaps from missing reports.
// ARM exclusive reservations may span neighboring bytes and cause retries.
// X86 CAS mismatch may write the same target value back; no readonly CAS claim.
//
//go:noescape
func atomicWrite8At(p unsafe.Pointer, v uint32)

//go:noescape
func atomicWrite16At(p unsafe.Pointer, v uint32)

//go:noescape
func atomicCmp8At(p unsafe.Pointer, expected, replacement uint32) uint32

//go:noescape
func atomicCmp16At(p unsafe.Pointer, expected, replacement uint32) uint32
