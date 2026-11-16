package store_test

import (
	"encoding/json"
	"fmt"
	"runtime/metrics"
)

func sampleRuntimeMetrics() map[string]any {
	names := []string{"/cpu/classes/gc/total:cpu-seconds", "/gc/cycles/total:gc-cycles", "/gc/heap/allocs:bytes", "/sched/latencies:seconds"}
	samples := make([]metrics.Sample, len(names))
	for i, n := range names {
		samples[i].Name = n
	}
	metrics.Read(samples)
	out := map[string]any{}
	for _, s := range samples {
		switch s.Value.Kind() {
		case metrics.KindFloat64:
			out[s.Name] = s.Value.Float64()
		case metrics.KindUint64:
			out[s.Name] = s.Value.Uint64()
		case metrics.KindFloat64Histogram:
			h := s.Value.Float64Histogram()
			out[s.Name] = map[string]any{"counts": append([]uint64(nil), h.Counts...), "buckets": fmt.Sprint(h.Buckets)}
		default:
			panic("unsupported metric " + s.Name)
		}
	}
	return out
}
func storeRuntimeMetrics(start map[string]any) {
	end := sampleRuntimeMetrics()
	a, _ := json.Marshal(start)
	b, _ := json.Marshal(end)
	fx.rec.Set("runtime_metrics_start", string(a))
	fx.rec.Set("runtime_metrics_end", string(b))
}
