//go:build !linux && !darwin

package forklimit

func memoryLimits() []uint64 { return nil }
