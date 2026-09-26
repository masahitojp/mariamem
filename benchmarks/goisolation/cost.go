package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

type member struct {
	RSS int64   `json:"rss_bytes"`
	CPU float64 `json:"cpu_seconds"`
}
type observation struct {
	At         float64           `json:"at_seconds"`
	RSS        int64             `json:"rss_bytes"`
	RunnerRSS  int64             `json:"runner_rss_bytes"`
	TreeRSS    int64             `json:"process_tree_rss_bytes"`
	Members    map[string]member `json:"members"`
	Collection float64           `json:"collection_seconds"`
}

func cpuClock(text string) (float64, error) {
	days := 0.0
	if before, after, ok := strings.Cut(text, "-"); ok {
		var err error
		days, err = strconv.ParseFloat(before, 64)
		if err != nil {
			return 0, err
		}
		text = after
	}
	total := 0.0
	for _, field := range strings.Split(text, ":") {
		value, err := strconv.ParseFloat(field, 64)
		if err != nil {
			return 0, err
		}
		total = total*60 + value
	}
	return days*86400 + total, nil
}
func parseProcesses(text string, parent, excluded int) (observation, error) {
	type entry struct {
		pid, ppid int
		value     member
	}
	entries := []entry{}
	for _, line := range strings.Split(text, "\n") {
		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}
		if len(fields) != 4 {
			return observation{}, fmt.Errorf("invalid ps row: %q", line)
		}
		pid, e1 := strconv.Atoi(fields[0])
		ppid, e2 := strconv.Atoi(fields[1])
		rss, e3 := strconv.ParseInt(fields[2], 10, 64)
		cpu, e4 := cpuClock(fields[3])
		if e1 != nil || e2 != nil || e3 != nil || e4 != nil {
			return observation{}, fmt.Errorf("invalid ps counters: %q", line)
		}
		entries = append(entries, entry{pid, ppid, member{rss * 1024, cpu}})
	}
	selected := map[int]bool{parent: true}
	for {
		changed := false
		for _, row := range entries {
			if selected[row.ppid] && row.pid != excluded && !selected[row.pid] {
				selected[row.pid] = true
				changed = true
			}
		}
		if !changed {
			break
		}
	}
	result := observation{Members: map[string]member{}}
	for _, row := range entries {
		if row.pid == parent {
			result.RunnerRSS = row.value.RSS
		}
		if selected[row.pid] && row.pid != parent && row.pid != excluded {
			result.Members[strconv.Itoa(row.pid)] = row.value
			result.RSS += row.value.RSS
		}
	}
	result.TreeRSS = result.RSS + result.RunnerRSS
	return result, nil
}
func readCost() (observation, error) {
	begin := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "ps", "-axo", "pid=,ppid=,rss=,time=")
	var output strings.Builder
	cmd.Stdout = &output
	if err := cmd.Start(); err != nil {
		return observation{}, err
	}
	pid := cmd.Process.Pid
	if err := cmd.Wait(); err != nil {
		return observation{}, err
	}
	row, err := parseProcesses(output.String(), os.Getpid(), pid)
	row.Collection = time.Since(begin).Seconds()
	return row, err
}

type sampler struct {
	baseline observation
	samples  []observation
	errors   []string
	interval time.Duration
	stop     chan struct{}
	done     sync.WaitGroup
}

func newSampler(interval time.Duration) (*sampler, error) {
	row, err := readCost()
	return &sampler{baseline: row, interval: interval, stop: make(chan struct{})}, err
}
func (s *sampler) start(begin time.Time) {
	s.done.Add(1)
	go func() {
		defer s.done.Done()
		for {
			row, err := readCost()
			if err != nil {
				s.errors = append(s.errors, err.Error())
				return
			}
			row.At = time.Since(begin).Seconds()
			s.samples = append(s.samples, row)
			select {
			case <-s.stop:
				return
			case <-time.After(s.interval):
			}
		}
	}()
}
func (s *sampler) finish(ready float64) map[string]any {
	close(s.stop)
	s.done.Wait()
	maxCPU := map[string]float64{}
	var peak, treePeak int64
	var nearest *observation
	for i := range s.samples {
		row := &s.samples[i]
		if row.RSS > peak {
			peak = row.RSS
		}
		if row.TreeRSS > treePeak {
			treePeak = row.TreeRSS
		}
		if nearest == nil || abs(row.At-ready) < abs(nearest.At-ready) {
			nearest = row
		}
		for pid, v := range row.Members {
			if v.CPU > maxCPU[pid] || maxCPU[pid] == 0 {
				maxCPU[pid] = v.CPU
			}
		}
	}
	var cpu any
	if len(maxCPU) > 0 {
		sum := 0.0
		for pid, value := range maxCPU {
			delta := value - s.baseline.Members[pid].CPU
			if delta > 0 {
				sum += delta
			}
		}
		cpu = sum
	}
	var rss, tree any
	if len(s.samples) > 0 {
		rss = peak
		tree = treePeak
	}
	return map[string]any{"mechanism": "ps runtime descendants excluding Go runner and sampling ps; runner RSS recorded separately", "requested_interval_seconds": s.interval.Seconds(), "baseline": s.baseline, "samples": s.samples, "errors": s.errors, "nearest_ready_sample": nearest, "sampled_descendant_cpu_seconds": cpu, "sampled_peak_rss_bytes": rss, "sampled_process_tree_peak_rss_bytes": tree}
}
func abs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}
func selfCPU() *float64 {
	var usage syscall.Rusage
	if syscall.Getrusage(syscall.RUSAGE_SELF, &usage) != nil {
		return nil
	}
	value := float64(usage.Utime.Sec+usage.Stime.Sec) + float64(usage.Utime.Usec+usage.Stime.Usec)/1e6
	return &value
}

func cpuDelta(before *float64) any {
	after := selfCPU()
	if before == nil || after == nil {
		return nil
	}
	return *after - *before
}
