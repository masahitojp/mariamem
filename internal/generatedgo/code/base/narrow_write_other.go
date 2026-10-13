//go:build !((darwin && arm64) || (linux && amd64))

package base

import "unsafe"

func atomicWrite8At(unsafe.Pointer, uint32)  { panic("mariamem: unsupported narrow atomic platform") }
func atomicWrite16At(unsafe.Pointer, uint32) { panic("mariamem: unsupported narrow atomic platform") }
func atomicCmp8At(unsafe.Pointer, uint32, uint32) uint32 {
	panic("mariamem: unsupported narrow atomic platform")
}
func atomicCmp16At(unsafe.Pointer, uint32, uint32) uint32 {
	panic("mariamem: unsupported narrow atomic platform")
}
