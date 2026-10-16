// Snapshot allocation diagnostic. GC is after measured boundaries only.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"strings"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func main() {
	out := flag.String("out", "", "fresh trial output")
	flag.Parse()
	must(os.MkdirAll(*out, 0700))
	must(os.Setenv("MARIAMEM_TIMING_DIR", *out))
	runtime.MemProfileRate = 65536
	traces := []timing.Trace{}
	ctx := timing.WithRecorder(context.Background(), func(t timing.Trace) { traces = append(traces, t) })
	db, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	conn, e := sql.Open("mysql", db.DSN())
	must(e)
	_, e = conn.Exec("CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB")
	must(e)
	args := []any{}
	values := []string{}
	for i := 0; i < 1000; i++ {
		values = append(values, "(?,?)")
		args = append(args, i, strings.Repeat("x", 32))
	}
	_, e = conn.Exec("INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...)
	must(e)
	must(conn.Close())
	must(db.WaitDisconnected(ctx))
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	start := time.Now()
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(e)
	elapsed := time.Since(start)
	runtime.ReadMemStats(&after)
	// Collection only after all measured boundaries, to settle alloc-space profile epoch.
	runtime.GC()
	f, e := os.Create(filepath.Join(*out, "snapshot.heap"))
	must(e)
	must(pprof.WriteHeapProfile(f))
	must(f.Close())

	child, e := snap.Fork(context.Background())
	must(e)
	pool, e := sql.Open("mysql", child.DSN())
	must(e)
	var count int
	must(pool.QueryRow("SELECT COUNT(*) FROM benchmark_rows").Scan(&count))
	if count != 1000 {
		panic(count)
	}
	must(pool.Close())
	must(child.WaitDisconnected(context.Background()))
	must(child.Close())
	must(snap.Close())
	result := map[string]any{"snapshot_seconds": elapsed.Seconds(), "go_total_alloc_delta": after.TotalAlloc - before.TotalAlloc, "backing": "process-local-heap", "persisted_inventory": nil, "traces": traces, "fork_count": count}
	b, e := json.MarshalIndent(result, "", "  ")
	must(e)
	must(os.WriteFile(filepath.Join(*out, "result.json"), b, 0600))
}
