package snapshot

import (
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

func TestVerifyIndependentBoundAndOrderedErrors(t *testing.T) {
	var active, peak, calls atomic.Int32
	first, later := errors.New("first"), errors.New("later")
	err := VerifyIndependent(11, func(i int) error {
		n := active.Add(1)
		for old := peak.Load(); n > old && !peak.CompareAndSwap(old, n); old = peak.Load() {
		}
		defer active.Add(-1)
		calls.Add(1)
		time.Sleep(time.Millisecond)
		if i == 0 {
			time.Sleep(5 * time.Millisecond)
			return first
		}
		if i == 1 {
			return later
		}
		return nil
	})
	if !errors.Is(err, first) || calls.Load() != 11 || peak.Load() != 2 || active.Load() != 0 {
		t.Fatalf("err=%v calls=%d peak=%d active=%d", err, calls.Load(), peak.Load(), active.Load())
	}
	for _, count := range []int{0, 1, 2, 17} {
		t.Run(fmt.Sprint(count), func(t *testing.T) {
			visited := make([]int, count)
			if err := VerifyIndependent(count, func(i int) error { visited[i]++; return nil }); err != nil {
				t.Fatal(err)
			}
			for i, n := range visited {
				if n != 1 {
					t.Fatalf("item %d checked %d times", i, n)
				}
			}
		})
	}
}
