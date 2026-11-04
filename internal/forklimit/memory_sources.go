package forklimit

import (
	"math"
	"strconv"
	"strings"
)

// memoryBytes checks units before multiplication. Zero/unrepresentable values
// are unavailable, not memory budgets; Resolve uses only values below MaxInt64.
func memoryBytes(total, unit uint64) uint64 {
	if total == 0 || unit == 0 || total > (math.MaxInt64-1)/unit {
		return 0
	}
	return total * unit
}

// memTotalBytes reads only the exact MemTotal KiB field. Invalid/duplicate fields
// cannot silently become a different memory observation. Kept portable for tests.
func memTotalBytes(raw []byte) uint64 {
	var total uint64
	found := false
	for line := range strings.SplitSeq(string(raw), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 0 || fields[0] != "MemTotal:" {
			continue
		}
		if found || len(fields) != 3 || fields[2] != "kB" {
			return 0
		}
		found = true
		n, err := strconv.ParseUint(fields[1], 10, 64)
		if err != nil {
			return 0
		}
		total = memoryBytes(n, 1024)
	}
	return total
}

// linuxMemoryLimits keeps both valid physical observations, so a tighter proc
// view is not overridden by sysinfo. Either source may fail independently;
// readable cgroup limits still apply when both physical sources are unavailable.
// Resolve later includes GOMEMLIMIT and selects the minimum, with CPU fallback
// only when no finite memory observation remains. No live free-memory estimate.
func linuxMemoryLimits(sysinfo func() (uint64, uint64, error), readFile func(string) ([]byte, error)) []uint64 {
	var limits []uint64
	if total, unit, err := sysinfo(); err == nil {
		if n := memoryBytes(total, unit); n > 0 {
			limits = append(limits, n)
		}
	}
	if raw, err := readFile("/proc/meminfo"); err == nil {
		if n := memTotalBytes(raw); n > 0 {
			limits = append(limits, n)
		}
	}
	cgroups, cgErr := readFile("/proc/self/cgroup")
	mounts, mountErr := readFile("/proc/self/mountinfo")
	if cgErr == nil && mountErr == nil {
		limits = append(limits, cgroupLimits(string(cgroups), string(mounts), readFile)...)
	}
	return limits
}
