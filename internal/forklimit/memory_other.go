//go:build !linux && !darwin && !windows

package forklimit

func memoryLimits() []uint64 { return nil }
