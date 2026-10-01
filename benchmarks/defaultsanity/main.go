// Informational default-runtime probe. No performance thresholds or tuning.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
)

func main() {
	runs := flag.Int("trials", 10, "independent starts and children")
	probe := flag.String("counter", "", "compiled benchmarks/tools/process_cost.c")
	output := flag.String("json", "", "result path")
	flag.Parse()
	if *runs < 1 || *probe == "" || *output == "" {
		panic("trials, counter and json required")
	}
	if os.Getenv("MARIAMEM_NATIVE_DIR") != "" || os.Getenv("MARIAMEM_RUNTIME") != "" {
		panic("clear runtime overrides")
	}
	dir, err := os.MkdirTemp("", "mariamem-default-timing-")
	must(err)
	defer os.RemoveAll(dir)
	must(os.Setenv("MARIAMEM_TIMING_DIR", dir))
	var rows []map[string]any
	counter := func(pids ...int) any {
		args := make([]string, len(pids))
		for i, p := range pids {
			args[i] = strconv.Itoa(p)
		}
		data, err := exec.Command(*probe, args...).Output()
		must(err)
		var result any
		must(json.Unmarshal(data, &result))
		return result
	}
	start := func(saved *mariamem.Snapshot, mode string) *mariamem.Database {
		before := counter(os.Getpid())
		var traces []timing.Trace
		pid := 0
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		ctx = timing.WithRecorder(ctx, func(t timing.Trace) {
			traces = append(traces, t)
			if t.RuntimePID > 0 {
				pid = t.RuntimePID
			}
		})
		begin := time.Now()
		var db *mariamem.Database
		var err error
		if saved == nil {
			db, err = mariamem.Start(ctx, mariamem.Options{})
		} else {
			db, err = saved.Fork(ctx)
		}
		must(err)
		pool, err := sql.Open("mysql", db.DSN())
		must(err)
		query, want := "SELECT 1", 1
		if saved != nil {
			query, want = "SELECT COUNT(*) FROM benchmark_rows", 1000
		}
		var n int
		must(pool.QueryRowContext(ctx, query).Scan(&n))
		if n != want {
			panic(n)
		}
		elapsed := time.Since(begin).Seconds() * 1000
		row := map[string]any{"case": mode, "latency_ms": elapsed, "before": before, "ready": counter(os.Getpid(), pid), "parent_pid": os.Getpid(), "runtime_pid": pid, "traces": traces}
		must(pool.Close())
		must(db.WaitDisconnected(ctx))
		rows = append(rows, row)
		fmt.Printf("%s %.3f ms\n", mode, elapsed)
		return db
	}
	for i := 0; i < *runs; i++ {
		db := start(nil, "start")
		must(db.Close())
		rows[len(rows)-1]["after_close"] = counter(os.Getpid())
	}
	ctx := context.Background()
	base, err := mariamem.Start(ctx, mariamem.Options{})
	must(err)
	pool, err := sql.Open("mysql", base.DSN())
	must(err)
	_, err = pool.Exec("CREATE TABLE benchmark_rows(id INT PRIMARY KEY, value INT)")
	must(err)
	tx, err := pool.Begin()
	must(err)
	for i := 0; i < 1000; i++ {
		_, err = tx.Exec("INSERT INTO benchmark_rows VALUES(?,?)", i, i)
		must(err)
	}
	must(tx.Commit())
	must(pool.Close())
	must(base.WaitDisconnected(ctx))
	saved, err := base.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(err)
	defer saved.Close()
	for i := 0; i < *runs; i++ {
		db := start(saved, "fork")
		must(db.Close())
		rows[len(rows)-1]["after_close"] = counter(os.Getpid())
	}
	data, err := json.MarshalIndent(map[string]any{"runtime": "generated-go", "boundary": "Go Options{} public API to first SQL; dedicated image provisioning included", "trials": *runs, "samples": rows}, "", "  ")
	must(err)
	must(os.WriteFile(*output, append(data, '\n'), 0600))
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
