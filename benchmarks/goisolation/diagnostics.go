package main

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// Read already-validated inventory metadata outside the Snapshot timer; no rehash.
func snapshotDiagnostics(path string) map[string]any {
	raw, err := os.ReadFile(filepath.Join(path, "manifest.json"))
	if err != nil {
		return map[string]any{"unavailable": err.Error()}
	}
	var manifest snapshot.Manifest
	if err = json.Unmarshal(raw, &manifest); err != nil {
		return map[string]any{"unavailable": err.Error()}
	}
	files := map[string]int64{}
	var total int64
	for name, entry := range manifest.Entries {
		if entry.Bytes != nil {
			files[name] = *entry.Bytes
			total += *entry.Bytes
		}
	}
	return map[string]any{"data_bytes": total, "file_bytes": files, "source": "already-validated snapshot inventory"}
}

// Collected after readiness and after the cost sampler stops, once per case.
// These slow observations must not be interpreted as instantaneous startup RSS.
func processDiagnostics(row map[string]any) map[string]any {
	begin, cpu := time.Now(), selfCPU()
	defer func() {
		row["diagnostic_seconds"] = time.Since(begin).Seconds()
		row["diagnostic_runner_cpu_seconds"] = cpuDelta(cpu)
	}()
	stages, ok := row["stage_timings"].(map[string]any)
	if !ok {
		return map[string]any{"error": "host stages required"}
	}
	trace, ok := stages["host"].(*timing.Trace)
	if !ok || trace == nil || trace.RuntimePID <= 0 {
		return map[string]any{"error": "runtime PID absent"}
	}
	pid := strconv.Itoa(trace.RuntimePID)
	out := map[string]any{"runtime_pid": trace.RuntimePID, "phase": "after_first_sql; sampler stopped; before close", "platform": runtime.GOOS}
	read := func(name, path string) {
		b, err := os.ReadFile(path)
		if err != nil {
			out[name] = map[string]any{"unavailable": err.Error()}
			return
		}
		if len(b) > 1024*1024 {
			b = b[:1024*1024]
			out[name+"_truncated"] = true
		}
		out[name] = string(b)
	}
	command := func(name string, args ...string) {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		b, err := exec.CommandContext(ctx, args[0], args[1:]...).CombinedOutput()
		if len(b) > 1024*1024 {
			b = b[:1024*1024]
			out[name+"_truncated"] = true
		}
		value := map[string]any{"command": args, "output": string(b)}
		if err != nil {
			value["unavailable"] = err.Error()
		}
		out[name] = value
	}
	if runtime.GOOS == "linux" {
		base := filepath.Join("/proc", pid)
		read("smaps", filepath.Join(base, "smaps"))
		read("smaps_rollup", filepath.Join(base, "smaps_rollup"))
		read("status", filepath.Join(base, "status"))
		entries, err := os.ReadDir(filepath.Join(base, "task"))
		if err != nil {
			out["thread_inventory_error"] = err.Error()
		} else {
			threads := []map[string]any{}
			for _, entry := range entries {
				if !entry.IsDir() {
					continue
				}
				thread := map[string]any{"tid": entry.Name()}
				for _, name := range []string{"comm", "stat", "wchan"} {
					b, e := os.ReadFile(filepath.Join(base, "task", entry.Name(), name))
					if e != nil {
						thread[name+"_error"] = e.Error()
					} else {
						thread[name] = strings.TrimSpace(string(b))
					}
				}
				threads = append(threads, thread)
			}
			out["threads"] = threads
		}
	} else if runtime.GOOS == "darwin" {
		command("vmmap_summary", "vmmap", "-summary", pid)
		command("threads", "ps", "-M", "-p", pid)
	} else {
		out["unavailable"] = "OS mapping diagnostic not implemented"
	}
	return out
}
