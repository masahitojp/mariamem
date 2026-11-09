package nativewire

import (
	"errors"
	"math"
	"testing"
	"time"
)

func TestTimeoutPublicDomain(t *testing.T) {
	for _, d := range []time.Duration{0, 1, 999999, time.Millisecond, 30 * time.Second, 30*time.Second + 1, time.Duration(math.MaxInt64)} {
		got, e := TimeoutNanos(d)
		want := d
		if d == 0 {
			want = 30 * time.Second
		}
		if e != nil || got != uint64(want) {
			t.Fatal(d, got, want, e)
		}
	}
	for _, d := range []time.Duration{-1, time.Duration(math.MinInt64)} {
		if _, e := TimeoutNanos(d); !errors.Is(e, ErrTimeout) {
			t.Fatal(d, e)
		}
	}
}
func TestTimeoutFixtureOverflow(t *testing.T) {
	max := uint64(math.MaxInt64) / uint64(time.Millisecond)
	for _, ms := range []uint64{0, 1, 99, 100, 10000, 30000, max} {
		d, e := TimeoutMilliseconds(ms)
		if e != nil || uint64(d) != ms*uint64(time.Millisecond) {
			t.Fatal(ms, d, e)
		}
	}
	for _, ms := range []uint64{max + 1, math.MaxUint64} {
		if _, e := TimeoutMilliseconds(ms); !errors.Is(e, ErrTimeout) {
			t.Fatal(ms, e)
		}
	}
}
