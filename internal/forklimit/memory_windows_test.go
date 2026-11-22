package forklimit

import "testing"

func TestWindowsNativeMemoryObservation(t *testing.T) {
	limits := memoryLimits()
	if len(limits) == 0 {
		t.Fatal("physical RAM unavailable")
	}
	for _, limit := range limits {
		if limit == 0 {
			t.Fatal("zero memory limit")
		}
	}
}
