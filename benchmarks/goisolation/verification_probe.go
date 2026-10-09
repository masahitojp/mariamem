package main

// Diagnostic experiments only. Production Resolve/Validate are never replaced.
import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
	"syscall"
	"time"

	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/runtimekind"
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

func (r *runner) verificationRun() (err error) {
	if r.cfg.stages {
		return errors.New("isolated verification requires diagnostics off")
	}
	db, _, err := r.startup(nil, time.Now())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, db.Close()) }()
	if err = r.seed(db); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	root, err := os.MkdirTemp("", "mariamem-verification-")
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, os.RemoveAll(root)) }()
	snapshotPath := filepath.Join(root, "prepared")
	if err = db.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Destination: snapshotPath})
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, saved.Close()) }()
	manifest, err := snapshot.Validate(snapshotPath, runtimekind.GuestSHA256)
	if err != nil {
		return err
	}
	snapshotItems := []hashItem{}
	for name, entry := range manifest.Entries {
		if entry.Kind == "file" {
			snapshotItems = append(snapshotItems, hashItem{filepath.Join(snapshotPath, "data", filepath.FromSlash(name)), *entry.Bytes, entry.SHA256})
		}
	}
	sort.Slice(snapshotItems, func(i, j int) bool { return snapshotItems[i].Path < snapshotItems[j].Path })
	r.verificationEnvironment = map[string]any{"snapshot_items": snapshotItems,
		"boundary":                 "external prepared-state validation component of acquisition; not Fork-time validation or complete copy/import latency",
		"snapshot_mode":            "explicit diagnostic output plus independent owned backing",
		"snapshot_inventory_count": len(manifest.Entries), "algorithm": "Go standard crypto/sha256 via production snapshot.Digest",
		"gomaxprocs": runtime.GOMAXPROCS(0), "godebug": os.Getenv("GODEBUG"),
		"goamd64_env": os.Getenv("GOAMD64"),
		"go_target":   environmentCommand("go", "env", "GOAMD64", "GOARM64", "GOOS", "GOARCH"),
		"filesystem":  environmentCommand("df", "-h", snapshotPath),
		"mounts":      environmentCommand("mount")}
	if runtime.GOOS == "linux" {
		r.verificationEnvironment["cpu"] = environmentCommand("lscpu")
		r.verificationEnvironment["filesystem_type"] = environmentCommand("df", "-T", snapshotPath)
	} else {
		r.verificationEnvironment["cpu"] = environmentCommand("sysctl", "hw.model", "hw.ncpu", "hw.optional.arm.FEAT_SHA256", "hw.optional.arm.FEAT_SHA512")
	}
	type condition struct {
		name      string
		workers   int
		operation func() error
		items     []hashItem
	}
	conditions := []condition{
		{"snapshot_full", 1, func() error { _, e := snapshot.Validate(snapshotPath, runtimekind.GuestSHA256); return e }, snapshotItems},
	}
	for _, dataset := range []struct {
		name  string
		items []hashItem
	}{{"snapshot_hashes", snapshotItems}} {
		for _, workers := range []int{1, 2, 4} {
			conditions = append(conditions, condition{dataset.name, workers, func() error { return hashItems(dataset.items, workers) }, dataset.items})
		}
	}
	for _, phase := range []string{"warmup", "measurement"} {
		rounds := r.cfg.runs
		if phase == "warmup" {
			rounds = r.cfg.warmup
		}
		for round := 0; round < rounds; round++ {
			for offset := range conditions {
				// Rotate and reverse order; no eviction or artificial cold-cache claim.
				index := (offset + round) % len(conditions)
				if round%2 != 0 {
					index = len(conditions) - 1 - index
				}
				c := conditions[index]
				row, e := observeVerification(c.operation)
				row["case"], row["workers"], row["phase"], row["run"] = c.name, c.workers, phase, round
				row["files_hashed"] = len(c.items)
				var bytes int64
				for _, item := range c.items {
					bytes += item.Bytes
				}
				row["content_bytes_hashed"] = bytes
				r.samples = append(r.samples, row)
				if e != nil {
					return e
				}
			}
		}
	}
	// Recheck the full production contracts after all experiments.
	_, err = snapshot.Validate(snapshotPath, runtimekind.GuestSHA256)
	return err
}
