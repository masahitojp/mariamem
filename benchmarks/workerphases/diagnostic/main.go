package main

import (
	"github.com/masahitojp/mariamem/benchmarks/workerphases/runner"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"sync/atomic"
)

var phase atomic.Uint32
var counts [4][14]atomic.Int64
var peak atomic.Int64
var kinds = map[string]int{"spawn": 0, "exit": 1, "spin": 2, "yield": 3, "wait_start": 4, "wait_return_0": 5, "wait_return_1": 6, "wait_return_2": 7, "wait_ns": 8, "wait_woken_short": 9, "notify": 10, "woken": 11, "yield_oversubscribed": 12, "agents": 13}

func observe(kind string, n int64) {
	if kind == "agents" {
		for p := peak.Load(); n > p; p = peak.Load() {
			if peak.CompareAndSwap(p, n) {
				break
			}
		}
		return
	}
	counts[phase.Load()][kinds[kind]].Add(n)
}
func main() {
	base.WorkerObservation = observe
	runner.PhaseHook = func(s string) { phase.Store(map[string]uint32{"outside": 0, "fork": 1, "sql": 2, "close": 3}[s]) }
	runner.Diagnostic = func() any {
		out := map[string]any{"peak_live_spawned_agents": peak.Load()}
		for i, name := range []string{"outside", "fork", "sql", "close"} {
			c := map[string]int64{}
			for k, j := range kinds {
				if k != "agents" {
					c[k] = counts[i][j].Load()
				}
			}
			out[name] = c
		}
		return out
	}
	runner.Main()
}
