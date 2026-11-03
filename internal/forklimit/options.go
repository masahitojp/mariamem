package forklimit

import (
	"bytes"
	"encoding/json"
	"errors"
	"math"
	"runtime"
	"runtime/debug"
	"strconv"
	"time"
)

// MaxForks is shared by Go, Python and the private control protocol.
const MaxForks int64 = math.MaxInt32
const MaxWait = time.Duration(math.MaxInt32) * time.Second
const childBudget uint64 = 256 << 20

// DecodeCapacity must run inside a request handler, after framing/ID decoding.
// RawMessage prevents JSON integer overflow from terminating a shared host.
// Missing or zero is automatic on the private Go control boundary; Python
// rejects explicit zero before sending. null and non-integer tokens are invalid.
func DecodeCapacity(raw json.RawMessage) (int, error) {
	if len(raw) == 0 {
		return 0, nil
	}
	raw = bytes.TrimSpace(raw)
	var n json.Number
	if len(raw) == 0 || raw[0] == '"' || json.Unmarshal(raw, &n) != nil || n == "" {
		return 0, errors.New("max_forks must be an integer between 0 and 2147483647")
	}
	v, err := strconv.ParseInt(string(n), 10, 64)
	if err != nil || v < 0 || v > MaxForks {
		return 0, errors.New("max_forks must be an integer between 0 and 2147483647")
	}
	return int(v), nil
}

// DecodeWait validates the new private capacity-wait field only. It does not
// change existing startup/query timeouts or Go context deadline semantics.
func DecodeWait(raw json.RawMessage) (time.Duration, error) {
	var s string
	if json.Unmarshal(raw, &s) != nil || s == "" {
		return 0, errors.New("fork timeout must be a positive bounded duration string")
	}
	d, err := time.ParseDuration(s)
	if err != nil || d <= 0 || d > MaxWait {
		return 0, errors.New("fork timeout must be positive and at most 2147483647 seconds")
	}
	return d, nil
}

// Resolve is evaluated once per capture. It is a memory-budget heuristic, not a
// CPU/latency optimum, free-memory monitor or process-wide/OOM guarantee.
func Resolve(explicit int) (int, error) {
	if explicit < 0 || int64(explicit) > MaxForks {
		return 0, errors.New("max_forks must be between 0 and 2147483647")
	}
	if explicit > 0 {
		return explicit, nil
	}
	limits := memoryLimits()
	if limit := debug.SetMemoryLimit(-1); limit > 0 && limit < math.MaxInt64 {
		limits = append(limits, uint64(limit))
	}
	return resolve(limits, runtime.GOMAXPROCS(0)), nil
}

func resolve(limits []uint64, cpus int) int {
	var selected uint64
	for _, n := range limits {
		if n > 0 && n < math.MaxInt64 && (selected == 0 || n < selected) {
			selected = n
		}
	}
	if selected == 0 {
		return int(min(uint64(max(1, cpus)), uint64(MaxForks)))
	}
	return int(min(max(uint64(1), selected/4/childBudget), uint64(MaxForks)))
}
