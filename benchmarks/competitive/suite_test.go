package main

import "testing"

func TestSuiteCPUClock(t *testing.T) {
	for raw, want := range map[string]float64{"0:01.23": 1.23, "01:02:03": 3723} {
		got, err := clockSeconds(raw)
		if err != nil || got != want {
			t.Fatalf("%s: %f %v", raw, got, err)
		}
	}
	if _, err := clockSeconds("bad"); err == nil {
		t.Fatal("invalid CPU clock accepted")
	}
}
