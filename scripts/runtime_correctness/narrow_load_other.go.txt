//go:build !((darwin && arm64) || (linux && amd64))

package base

import "unsafe"

func atomicRead8At(unsafe.Pointer) uint32 { panic("mariamem: unsupported narrow atomic platform") }
func atomicRead16At(unsafe.Pointer) uint32 { panic("mariamem: unsupported narrow atomic platform") }
