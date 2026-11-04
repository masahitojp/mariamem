package forklimit

import (
	"path"
	"strconv"
	"strings"
)

// Kept portable so nested cgroup policy is tested on both supported hosts.
// Resolve process membership against the actual mount root, then include every
// visible ancestor limit. Missing/unreadable/malformed/unlimited values are not
// interpreted as memory. Namespace-hidden ancestors are not observable here.
func cgroupLimits(memberships, mounts string, readFile func(string) ([]byte, error)) []uint64 {
	type group struct {
		where string
		v2    bool
	}
	var groups []group
	for line := range strings.SplitSeq(memberships, "\n") {
		f := strings.SplitN(line, ":", 3)
		if len(f) != 3 || !strings.HasPrefix(f[2], "/") {
			continue
		}
		if f[0] == "0" && f[1] == "" {
			groups = append(groups, group{f[2], true})
		} else if hasWord(f[1], "memory") {
			groups = append(groups, group{f[2], false})
		}
	}
	var limits []uint64
	for line := range strings.SplitSeq(mounts, "\n") {
		parts := strings.SplitN(line, " - ", 2)
		if len(parts) != 2 {
			continue
		}
		left, right := strings.Fields(parts[0]), strings.Fields(parts[1])
		if len(left) < 6 || len(right) < 3 {
			continue
		}
		v2 := right[0] == "cgroup2"
		if !v2 && (right[0] != "cgroup" || !hasWord(right[2], "memory")) {
			continue
		}
		root, mount := unescapeMount(left[3]), unescapeMount(left[4])
		if !strings.HasPrefix(root, "/") || !strings.HasPrefix(mount, "/") {
			continue
		}
		root, mount = path.Clean(root), path.Clean(mount)
		for _, g := range groups {
			if g.v2 != v2 {
				continue
			}
			where := path.Clean(g.where)
			if where != root && root != "/" && !strings.HasPrefix(where, root+"/") {
				continue
			}
			rel := strings.TrimPrefix(where, root)
			current := path.Join(mount, rel)
			name := "memory.limit_in_bytes"
			if v2 {
				name = "memory.max"
			}
			for {
				if raw, err := readFile(path.Join(current, name)); err == nil {
					if n, err := strconv.ParseUint(strings.TrimSpace(string(raw)), 10, 64); err == nil && n > 0 {
						// v1 reports PAGE_COUNTER_MAX (LONG_MAX rounded down
						// to pages) rather than the v2 literal "max".
						if v2 || n < (uint64(1)<<63)-4096 {
							limits = append(limits, n)
						}
					}
				}
				if current == mount {
					break
				}
				next := path.Dir(current)
				if next == current {
					break
				}
				current = next
			}
		}
	}
	return limits
}

func hasWord(list, word string) bool {
	for item := range strings.SplitSeq(list, ",") {
		if item == word {
			return true
		}
	}
	return false
}

func unescapeMount(s string) string {
	return strings.NewReplacer(`\040`, " ", `\011`, "\t", `\012`, "\n", `\134`, `\`).Replace(s)
}
