package main

// Diagnostic experiments only. Production Resolve/Validate are never replaced.
import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"sync"
	"syscall"
	"time"

	"github.com/masahitojp/mariamem/internal/snapshot"
)

type hashItem struct {
	Path   string `json:"path"`
	Bytes  int64  `json:"bytes"`
	SHA256 string `json:"sha256"`
}

// Every item is hashed with the unchanged production Digest implementation.
// Each index has one owner; no worker shares a digest/buffer or trusts a cache.
func hashItems(items []hashItem, workers int) error {
	if workers < 1 {
		return errors.New("invalid hash worker count")
	}
	errorsByItem := make([]error, len(items))
	jobs := make(chan int)
	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for index := range jobs {
				item := items[index]
				info, err := os.Lstat(item.Path)
				if err == nil && (!info.Mode().IsRegular() || info.Size() != item.Bytes) {
					err = fmt.Errorf("item metadata mismatch: %s", item.Path)
				}
				if err == nil {
					var digest string
					digest, err = snapshot.Digest(item.Path)
					if err == nil && digest != item.SHA256 {
						err = fmt.Errorf("item hash mismatch: %s", item.Path)
					}
				}
				errorsByItem[index] = err
			}
		}()
	}
	for index := range items {
		jobs <- index
	}
	close(jobs)
	wg.Wait()
	return errors.Join(errorsByItem...)
}

func observeVerification(operation func() error) (map[string]any, error) {
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	cpu := selfCPU()
	begin := time.Now()
	err := operation()
	wall := time.Since(begin).Seconds()
	usedCPU := cpuDelta(cpu)
	runtime.ReadMemStats(&after)
	var usage syscall.Rusage
	var peak any
	if syscall.Getrusage(syscall.RUSAGE_SELF, &usage) == nil {
		bytes := int64(usage.Maxrss)
		if runtime.GOOS == "linux" {
			bytes *= 1024
		}
		peak = bytes
	}
	return map[string]any{"latency_seconds": wall, "cpu_seconds": usedCPU,
		"heap_total_allocated_bytes":        after.TotalAlloc - before.TotalAlloc,
		"heap_inuse_delta_bytes":            int64(after.HeapInuse) - int64(before.HeapInuse),
		"process_cumulative_peak_rss_bytes": peak}, err
}

func environmentCommand(name string, args ...string) map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, name, args...).CombinedOutput()
	if len(out) > 128*1024 {
		out = out[:128*1024]
	}
	result := map[string]any{"output": string(out)}
	if err != nil {
		result["error"] = err.Error()
	}
	return result
}

func (r *runner) verificationRun() error {
	return errors.New("external persisted-Snapshot verification probe is historical; current baselines are in memory")
}
