package main

import (
	"runtime"
	"runtime/metrics"
	"syscall"
	"time"
)

// Observational benchmark counters, never a product memory guarantee. The
// sampled Go heap excludes mmap and may miss peaks shorter than the interval.
func goResourcePoint() map[string]any {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return map[string]any{"heap_alloc_bytes": m.HeapAlloc, "heap_inuse_bytes": m.HeapInuse,
		"heap_sys_bytes": m.HeapSys, "heap_released_bytes": m.HeapReleased,
		"total_alloc_bytes": m.TotalAlloc, "mallocs": m.Mallocs, "num_gc": m.NumGC,
		"pause_total_ns": m.PauseTotalNs, "goroutines": runtime.NumGoroutine()}
}

func sampleGoResources() func() map[string]any {
	stop, done := make(chan struct{}), make(chan map[string]any, 1)
	before := goResourcePoint()
	go func() {
		ticker := time.NewTicker(25 * time.Millisecond)
		defer ticker.Stop()
		samples := []metrics.Sample{{Name: "/memory/classes/heap/objects:bytes"}}
		var peak uint64
		count := 0
		sample := func() {
			metrics.Read(samples)
			v := samples[0].Value.Uint64()
			if v > peak {
				peak = v
			}
			count++
		}
		sample()
		for {
			select {
			case <-ticker.C:
				sample()
			case <-stop:
				sample()
				var r syscall.Rusage
				must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
				rss := uint64(r.Maxrss)
				if runtime.GOOS == "linux" {
					rss *= 1024
				}
				after := goResourcePoint()
				done <- map[string]any{"before": before, "after": after, "sample_interval_ms": 25,
					"samples": count, "sampled_peak_go_heap_objects_bytes": peak, "process_peak_rss_bytes": rss,
					"cumulative_alloc_bytes": after["total_alloc_bytes"].(uint64) - before["total_alloc_bytes"].(uint64),
					"scope":                  "Go heap excludes mmap; RSS is OS process high-water, not allocation sum; after follows existing diagnostic GC"}
				return
			}
		}
	}()
	return func() map[string]any { close(stop); return <-done }
}
