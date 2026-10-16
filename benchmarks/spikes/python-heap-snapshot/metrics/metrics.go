// Resource campaign only. A per-process high-water mark is not a process-tree sum.
package metrics

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"syscall"
)

func Read() map[string]any {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	var r syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &r)
	return map[string]any{"pid": os.Getpid(), "total_alloc": m.TotalAlloc, "heap_alloc": m.HeapAlloc, "num_gc": m.NumGC, "maxrss_raw": r.Maxrss}
}
func Save() {
	dir := os.Getenv("MARIAMEM_SPIKE_METRICS")
	if dir == "" {
		return
	}
	m := Read()
	m["role"] = filepath.Base(os.Args[0])
	m["snapshot_info_helper"] = len(os.Args) > 1 && os.Args[1] == "--snapshot-info"
	b, e := json.MarshalIndent(m, "", "  ")
	if e == nil {
		e = os.WriteFile(filepath.Join(dir, fmt.Sprintf("%d.json", os.Getpid())), b, 0600)
	}
	if e != nil {
		fmt.Fprintln(os.Stderr, "metrics:", e)
	}
}
