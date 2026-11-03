package forklimit

import (
	"os"
	"strconv"
	"strings"
)

func memoryLimits() []uint64 {
	var limits []uint64
	if raw, err := os.ReadFile("/proc/meminfo"); err == nil {
		for line := range strings.SplitSeq(string(raw), "\n") {
			f := strings.Fields(line)
			if len(f) == 3 && f[0] == "MemTotal:" && f[2] == "kB" {
				if n, err := strconv.ParseUint(f[1], 10, 54); err == nil {
					limits = append(limits, n*1024)
				}
			}
		}
	}
	cgroups, cgErr := os.ReadFile("/proc/self/cgroup")
	mounts, mountErr := os.ReadFile("/proc/self/mountinfo")
	if cgErr == nil && mountErr == nil {
		limits = append(limits, cgroupLimits(string(cgroups), string(mounts), os.ReadFile)...)
	}
	return limits
}
