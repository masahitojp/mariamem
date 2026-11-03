package forklimit

import (
	"encoding/json"
	"errors"
	"math"
	"reflect"
	"testing"
	"time"
)

func TestCapacityTokens(t *testing.T) {
	for _, raw := range []string{"", "0", "1", "2147483647", " 2 "} {
		if _, err := DecodeCapacity(json.RawMessage(raw)); err != nil {
			t.Errorf("%q: %v", raw, err)
		}
	}
	for _, raw := range []string{"-1", "2147483648", "1267650600228229401496703205376", "1.0", "1e0", `"1"`, "true", "null", "[]", "{}"} {
		if _, err := DecodeCapacity(json.RawMessage(raw)); err == nil {
			t.Errorf("accepted %q", raw)
		}
	}
}

func TestWaitTokens(t *testing.T) {
	for raw, want := range map[string]time.Duration{`"1ns"`: 1, `"2147483647000000000ns"`: MaxWait} {
		if got, err := DecodeWait(json.RawMessage(raw)); err != nil || got != want {
			t.Fatalf("%s: %v %v", raw, got, err)
		}
	}
	for _, raw := range []string{"", "null", "true", "1", `"0ns"`, `"-1s"`, `"2147483647000000001ns"`, `"1267650600228229401496703205376s"`, `"NaNs"`, `"+Infs"`} {
		if _, err := DecodeWait(json.RawMessage(raw)); err == nil {
			t.Errorf("accepted %q", raw)
		}
	}
	if MaxWait+25*time.Second <= MaxWait {
		t.Fatal("watchdog margin overflow")
	}
}

func TestResolution(t *testing.T) {
	const GiB = uint64(1 << 30)
	for _, tc := range []struct {
		name       string
		limits     []uint64
		cpus, want int
	}{
		{"none", nil, 4, 4}, {"fallback floor", nil, 0, 1},
		{"unknown", []uint64{0, math.MaxInt64, math.MaxUint64}, 3, 3},
		{"tiny", []uint64{1}, 8, 1}, {"2GiB", []uint64{2 * GiB}, 8, 2},
		{"16GiB is memory not CPU", []uint64{16 * GiB}, 4, 16},
		{"minimum", []uint64{16 * GiB, 7 * GiB, 4 * GiB}, 8, 4},
		{"clamp", []uint64{math.MaxInt64 - 1}, 4, int(MaxForks)},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := resolve(tc.limits, tc.cpus); got != tc.want {
				t.Fatalf("%d != %d", got, tc.want)
			}
		})
	}
	if n, err := Resolve(3); err != nil || n != 3 {
		t.Fatal(n, err)
	}
	if n, err := Resolve(0); err != nil || n < 1 || int64(n) > MaxForks {
		t.Fatal(n, err)
	}
	for _, n := range []int{-1, int(MaxForks) + 1} {
		if _, err := Resolve(n); err == nil {
			t.Fatal("accepted", n)
		}
	}
}

func TestCgroupMountRootsAncestorsAndUnavailableLimits(t *testing.T) {
	for _, tc := range []struct {
		name, membership, mounts string
		files                    map[string]string
		want                     []uint64
	}{
		{"v2 nested", "0::/team/job", "1 2 0:1 / /sys/fs/cgroup rw - cgroup2 cgroup rw", map[string]string{
			"/sys/fs/cgroup/team/job/memory.max": "max", "/sys/fs/cgroup/team/memory.max": "4294967296", "/sys/fs/cgroup/memory.max": "8589934592",
		}, []uint64{4 << 30, 8 << 30}},
		{"v1 rooted mount", "4:cpu,cpuacct:/elsewhere\n5:memory:/team/job", "1 2 0:1 /team /cg/mem rw - cgroup cgroup rw,memory", map[string]string{
			"/cg/mem/job/memory.limit_in_bytes": "2147483648", "/cg/mem/memory.limit_in_bytes": "1073741824",
		}, []uint64{2 << 30, 1 << 30}},
		{"namespace root and escaped mount", "0::/", `1 2 0:1 / /cg\040space rw - cgroup2 cgroup rw`, map[string]string{"/cg space/memory.max": "123"}, []uint64{123}},
		{"unrelated mount", "0::/other/job", "1 2 0:1 /team /cg rw - cgroup2 cgroup rw", map[string]string{"/cg/memory.max": "123"}, nil},
		{"bad values", "0::/job", "1 2 0:1 / /cg rw - cgroup2 cgroup rw", map[string]string{"/cg/job/memory.max": "garbage", "/cg/memory.max": "0"}, nil},
		{"missing", "0::/job", "1 2 0:1 / /cg rw - cgroup2 cgroup rw", nil, nil},
		{"v1 unlimited sentinel", "5:memory:/job", "1 2 0:1 / /cg rw - cgroup cgroup rw,memory", map[string]string{
			"/cg/job/memory.limit_in_bytes": "9223372036854771712", "/cg/memory.limit_in_bytes": "9223372036854775807",
		}, nil},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var read []string
			got := cgroupLimits(tc.membership, tc.mounts, func(p string) ([]byte, error) {
				read = append(read, p)
				v, ok := tc.files[p]
				if !ok {
					return nil, errors.New("unavailable")
				}
				return []byte(v), nil
			})
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("%v != %v (reads %v)", got, tc.want, read)
			}
		})
	}
}
