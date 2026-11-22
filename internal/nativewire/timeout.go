package nativewire

import (
	"errors"
	"math"
	"time"
)

var ErrTimeout = errors.New("native query timeout must not be negative or overflow time.Duration")

// TimeoutNanos preserves the public Go duration domain,including submillisecond
// values. Zero selects the public30-second default;the wire carries no sentinel.
func TimeoutNanos(d time.Duration) (uint64, error) {
	if d < 0 {
		return 0, ErrTimeout
	}
	if d == 0 {
		d = 30 * time.Second
	}
	return uint64(d), nil
}

// TimeoutMilliseconds is only the historical experiment-fixture adapter.
// Checked multiplication prevents a uint64 fixture value wrapping a duration.
func TimeoutMilliseconds(ms uint64) (time.Duration, error) {
	if ms > uint64(math.MaxInt64)/uint64(time.Millisecond) {
		return 0, ErrTimeout
	}
	return time.Duration(ms) * time.Millisecond, nil
}
