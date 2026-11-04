package forklimit

import (
	"errors"
	"math"
	"reflect"
	"testing"
)

func TestMemoryByteUnitsAndOverflow(t *testing.T) {
	for _, c := range []struct{ total, unit, want uint64 }{
		{16 << 30, 1, 16 << 30}, {262144, 4096, 1 << 30}, {1, 1024, 1024},
		{0, 1, 0}, {1, 0, 0}, {math.MaxUint64, 2, 0}, {2, math.MaxUint64, 0},
		{math.MaxInt64, 1, 0}, {math.MaxInt64 - 1, 1, math.MaxInt64 - 1},
	} {
		if got := memoryBytes(c.total, c.unit); got != c.want {
			t.Fatalf("%d*%d: %d want %d", c.total, c.unit, got, c.want)
		}
	}
}

func TestMemTotalParser(t *testing.T) {
	for _, c := range []struct {
		name, raw string
		want      uint64
	}{
		{"KiB", "MemTotal: 16777216 kB\n", 16 << 30},
		{"whitespace", "MemFree: 4 kB\n\tMemTotal:\t2097152\tkB\r\nMemAvailable: 9 kB", 2 << 30},
		{"decimal-leading-zero", "MemTotal: 0001024 kB", 1 << 20},
		{"missing", "MemAvailable: 2097152 kB", 0},
		{"near-key", "MemTotalExtra: 2097152 kB", 0},
		{"wrong-unit", "MemTotal: 2097152 MB", 0},
		{"no-unit", "MemTotal: 2097152", 0},
		{"extra-field", "MemTotal: 2097152 kB bad", 0},
		{"negative", "MemTotal: -1 kB", 0},
		{"zero", "MemTotal: 0 kB", 0},
		{"not-number", "MemTotal: broken kB", 0},
		{"parse-overflow", "MemTotal: 18446744073709551616 kB", 0},
		{"byte-overflow", "MemTotal: 18446744073709551615 kB", 0},
		{"duplicate", "MemTotal: 1024 kB\nMemTotal: 2048 kB", 0},
		{"bad-duplicate", "MemTotal: 1024 kB\nMemTotal: broken kB", 0},
	} {
		t.Run(c.name, func(t *testing.T) {
			if got := memTotalBytes([]byte(c.raw)); got != c.want {
				t.Fatalf("%d want %d", got, c.want)
			}
		})
	}
}

func TestLinuxMemorySourcesAndFallback(t *testing.T) {
	const GiB = uint64(1 << 30)
	unavailable := errors.New("source unavailable")
	for _, c := range []struct {
		name          string
		total, unit   uint64
		sysErr        error
		proc          string
		cgroup        string
		goLimit       uint64
		cpus, wantCap int
		want          []uint64
	}{
		{name: "both sources tighter proc", total: 16 * GiB, unit: 1, proc: "MemTotal: 4194304 kB", cpus: 8, wantCap: 4, want: []uint64{16 * GiB, 4 * GiB}},
		{name: "tighter kernel", total: 2 * GiB, unit: 1, proc: "MemTotal: 16777216 kB", cpus: 8, wantCap: 2, want: []uint64{2 * GiB, 16 * GiB}},
		{name: "syscall denied proc survives", sysErr: unavailable, proc: "MemTotal: 2097152 kB", cpus: 8, wantCap: 2, want: []uint64{2 * GiB}},
		{name: "proc unreadable kernel survives", total: 16 * GiB, unit: 1, cpus: 8, wantCap: 16, want: []uint64{16 * GiB}},
		{name: "proc malformed kernel survives", total: 2 * GiB, unit: 1, proc: "MemTotal: broken kB", cpus: 8, wantCap: 2, want: []uint64{2 * GiB}},
		{name: "nonbyte kernel units", total: 262144, unit: 4096, cpus: 8, wantCap: 1, want: []uint64{GiB}},
		{name: "invalid kernel units use proc", total: 16 * GiB, unit: 0, proc: "MemTotal: 2097152 kB", cpus: 8, wantCap: 2, want: []uint64{2 * GiB}},
		{name: "overflow kernel use proc", total: math.MaxUint64, unit: 4096, proc: "MemTotal: 2097152 kB", cpus: 8, wantCap: 2, want: []uint64{2 * GiB}},
		{name: "both physical absent cgroup remains", sysErr: unavailable, cgroup: "2147483648", cpus: 8, wantCap: 2, want: []uint64{2 * GiB}},
		{name: "all physical absent Go limit remains", sysErr: unavailable, goLimit: 3 * GiB, cpus: 8, wantCap: 3},
		{name: "all unreadable CPU fallback", sysErr: unavailable, cpus: 4, wantCap: 4},
		{name: "invalid and unlimited CPU fallback", total: 0, unit: 1, proc: "MemTotal: -1 kB", cgroup: "max", cpus: 3, wantCap: 3},
		{name: "CPU fallback minimum one", sysErr: unavailable, cpus: 0, wantCap: 1},
		{name: "cgroup and Go tighter than physical", total: 16 * GiB, unit: 1, proc: "MemTotal: 8388608 kB", cgroup: "4294967296", goLimit: 2 * GiB, cpus: 8, wantCap: 2, want: []uint64{16 * GiB, 8 * GiB, 4 * GiB}},
	} {
		t.Run(c.name, func(t *testing.T) {
			files := map[string]string{}
			if c.proc != "" {
				files["/proc/meminfo"] = c.proc
			}
			if c.cgroup != "" {
				files["/proc/self/cgroup"] = "0::/job"
				files["/proc/self/mountinfo"] = "1 2 0:1 / /cg rw - cgroup2 cgroup rw"
				files["/cg/job/memory.max"] = c.cgroup
			}
			calls := 0
			limits := linuxMemoryLimits(func() (uint64, uint64, error) { calls++; return c.total, c.unit, c.sysErr }, func(path string) ([]byte, error) {
				if v, ok := files[path]; ok {
					return []byte(v), nil
				}
				return nil, unavailable
			})
			if calls != 1 || !reflect.DeepEqual(limits, c.want) {
				t.Fatalf("calls=%d limits=%v want %v", calls, limits, c.want)
			}
			if c.goLimit > 0 {
				limits = append(limits, c.goLimit)
			}
			if got := resolve(limits, c.cpus); got != c.wantCap {
				t.Fatalf("cap %d want %d from %v", got, c.wantCap, limits)
			}
		})
	}
}
