package main

// Experiment-only counters and child-window profiles. No runtime policy changes,
// forced GC, periodic sampler, or altered SQL. Disabled mode reads no metrics.
import (
	"encoding/json"
	"fmt"
	"os"
	"runtime/metrics"
	"runtime/pprof"
	"runtime/trace"
	"time"
)

type childAudit struct {
	path, mode string
	points     []map[string]any
	samples    []metrics.Sample
	file       *os.File
	start      time.Time
}

func newChildAudit(path, mode string, workers int) *childAudit {
	a := &childAudit{path: path, mode: mode, start: time.Now()}
	if mode != "none" && mode != "cpu" && mode != "trace" {
		panic("invalid child profile")
	}
	if path == "" {
		if mode != "none" {
			panic("profile requires child-audit")
		}
		return a
	}
	if workers != 1 {
		panic("child audit requires serial workload")
	}
	names := []string{
		"/cpu/classes/gc/mark/assist:cpu-seconds", "/cpu/classes/gc/mark/dedicated:cpu-seconds",
		"/cpu/classes/gc/mark/idle:cpu-seconds", "/cpu/classes/gc/pause:cpu-seconds",
		"/cpu/classes/gc/total:cpu-seconds", "/cpu/classes/total:cpu-seconds",
		"/cpu/classes/user:cpu-seconds", "/cpu/classes/scavenge/assist:cpu-seconds",
		"/cpu/classes/scavenge/background:cpu-seconds", "/cpu/classes/idle:cpu-seconds",
		"/gc/cycles/automatic:gc-cycles", "/gc/cycles/forced:gc-cycles",
		"/gc/heap/allocs:bytes", "/gc/heap/frees:bytes", "/gc/heap/goal:bytes",
		"/gc/heap/live:bytes", "/gc/scan/heap:bytes", "/gc/scan/stack:bytes",
		"/memory/classes/heap/objects:bytes", "/memory/classes/heap/free:bytes",
		"/memory/classes/heap/released:bytes", "/memory/classes/heap/unused:bytes",
		"/sync/mutex/wait/total:seconds", "/sched/goroutines:goroutines",
	}
	for _, n := range names {
		a.samples = append(a.samples, metrics.Sample{Name: n})
	}
	a.point("audit_start")
	return a
}

func (a *childAudit) point(name string) {
	if a.path == "" {
		return
	}
	metrics.Read(a.samples)
	v := map[string]any{"phase": name, "wall_seconds": time.Since(a.start).Seconds(), "process_cpu_seconds": cpu()}
	for _, s := range a.samples {
		switch s.Value.Kind() {
		case metrics.KindUint64:
			v[s.Name] = s.Value.Uint64()
		case metrics.KindFloat64:
			v[s.Name] = s.Value.Float64()
		default:
			panic(fmt.Sprintf("unsupported audit metric %s", s.Name))
		}
	}
	a.points = append(a.points, v)
}

func (a *childAudit) startChildren() {
	if a.mode != "none" {
		var err error
		a.file, err = os.Create(a.path + "." + a.mode)
		must(err)
		if a.mode == "cpu" {
			must(pprof.StartCPUProfile(a.file))
		} else {
			must(trace.Start(a.file))
		}
	}
	a.point("children_begin")
}

func (a *childAudit) stopChildren() {
	a.point("children_end")
	if a.file != nil {
		if a.mode == "cpu" {
			pprof.StopCPUProfile()
		} else {
			trace.Stop()
		}
		must(a.file.Close())
		a.file = nil
	}
}

func (a *childAudit) finish() {
	if a.path == "" {
		return
	}
	b, err := json.MarshalIndent(map[string]any{"profile": a.mode, "points": a.points,
		"scope": "operation-boundary runtime/metrics; CPU classes are Go estimates, not OS CPU; heap/live is last-GC live; no forced GC added"}, "", " ")
	must(err)
	must(os.WriteFile(a.path, b, 0600))
}
