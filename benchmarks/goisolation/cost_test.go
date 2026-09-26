package main

import "testing"

func TestCPUClock(t *testing.T) {
	for input, want := range map[string]float64{"00:00.25": .25, "02:03.50": 123.5, "01:02:03": 3723, "2-01:02:03.25": 176523.25} {
		got, err := cpuClock(input)
		if err != nil || got != want {
			t.Fatalf("%s: %v %v", input, got, err)
		}
	}
	if _, err := cpuClock("bad"); err == nil {
		t.Fatal("invalid CPU clock accepted")
	}
}
func TestProcessSelectionKeepsRunnerSeparate(t *testing.T) {
	table := "12 11 30 00:00.50\n10 1 100 00:03\n11 10 20 00:01\n20 1 900 00:20\n14 13 700 00:10\n13 10 800 00:11\n"
	row, err := parseProcesses(table, 10, 13)
	if err != nil {
		t.Fatal(err)
	}
	if len(row.Members) != 2 || row.RunnerRSS != 100*1024 || row.RSS != 50*1024 || row.TreeRSS != 150*1024 {
		t.Fatal(row)
	}
	if _, ok := row.Members["14"]; ok {
		t.Fatal("sampler descendants included")
	}
	if _, err := parseProcesses("invalid", 10, 13); err == nil {
		t.Fatal("malformed ps accepted")
	}
}
func TestUnavailableCostsAreNotInvented(t *testing.T) {
	s := &sampler{stop: make(chan struct{}), baseline: observation{Members: map[string]member{}}}
	row := s.finish(1)
	if row["sampled_peak_rss_bytes"] != nil || row["sampled_descendant_cpu_seconds"] != nil {
		t.Fatal(row)
	}
}
func TestExitedCPUAndNearestReady(t *testing.T) {
	s := &sampler{stop: make(chan struct{}), baseline: observation{Members: map[string]member{"11": {CPU: 1}}}, samples: []observation{{At: .5, TreeRSS: 100, Members: map[string]member{"11": {CPU: 2}, "12": {CPU: .5}}}, {At: 1, TreeRSS: 80, Members: map[string]member{"11": {CPU: 3}}}}}
	row := s.finish(1)
	if row["sampled_descendant_cpu_seconds"] != 2.5 || row["sampled_process_tree_peak_rss_bytes"] != int64(100) || row["nearest_ready_sample"].(*observation).At != 1 {
		t.Fatal(row)
	}
}
