// Informational public-API baseline, not go test benchmarks or performance gates.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
)

type config struct {
	native, output, workers              string
	runs, warmup, rows, queries, clients int
	interval, hold                       float64
	stages, guestStages                  bool
	initDiagnostics, memoryDiagnostics   bool
}
type runner struct {
	cfg           config
	samples       []map[string]any
	version       string
	captureMemory bool
}

func event(name string, begin time.Time) timing.Event {
	return timing.Event{Name: name, Offset: time.Since(begin).Nanoseconds()}
}
func (r *runner) startup(saved *mariamem.Snapshot, group time.Time) (db *mariamem.Database, row map[string]any, err error) {
	begin := time.Now()
	events := []timing.Event{event("begin", begin)}
	var host *timing.Trace
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	if r.cfg.stages {
		ctx = timing.WithRecorder(ctx, func(trace timing.Trace) { host = &trace })
	}
	if saved == nil {
		db, err = mariamem.Start(ctx, mariamem.Options{NativeDir: r.cfg.native})
	} else {
		db, err = saved.Fork(ctx)
	}
	if err != nil {
		return nil, nil, err
	}
	success := false
	owned := db
	defer func() {
		if !success {
			err = errors.Join(err, owned.Close())
			db = nil
		}
	}()
	events = append(events, event("database_returned", begin))
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return nil, nil, err
	}
	defer func() { err = errors.Join(err, pool.Close()) }()
	conn, err := pool.Conn(ctx)
	if err != nil {
		return nil, nil, err
	}
	defer conn.Close()
	events = append(events, event("client_connected", begin))
	query, expected := "SELECT 1", 1
	if saved != nil {
		query, expected = "SELECT COUNT(*) FROM benchmark_rows", r.cfg.rows
	}
	var value int
	if err = conn.QueryRowContext(ctx, query).Scan(&value); err != nil {
		return nil, nil, err
	}
	if value != expected {
		return nil, nil, fmt.Errorf("unexpected first SQL: %d != %d", value, expected)
	}
	ready := time.Now()
	events = append(events, event("first_sql", begin))
	var version string
	if err = conn.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version); err != nil {
		return nil, nil, err
	}
	var stages any
	if r.cfg.stages {
		if host == nil {
			return nil, nil, errors.New("missing host startup trace")
		}
		if r.cfg.guestStages && len(host.Guest) == 0 {
			return nil, nil, errors.New("matching instrumented guest required")
		}
		stages = map[string]any{"caller": events, "host": host}
	}
	row = map[string]any{"latency_seconds": ready.Sub(begin).Seconds(), "ready_at_seconds": ready.Sub(group).Seconds(), "server_version": version, "stage_timings": stages}
	success = true
	return db, row, nil
}
func (r *runner) seed(db *mariamem.Database) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, pool.Close()) }()
	if _, err = pool.ExecContext(ctx, "CREATE TABLE benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB"); err != nil {
		return err
	}
	tx, err := pool.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for start := 0; start < r.cfg.rows; start += 1000 {
		end := min(start+1000, r.cfg.rows)
		values := make([]string, 0, end-start)
		args := make([]any, 0, (end-start)*2)
		for i := start; i < end; i++ {
			values = append(values, "(?,?)")
			args = append(args, i, strings.Repeat("x", 32))
		}
		if _, err = tx.ExecContext(ctx, "INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...); err != nil {
			return err
		}
	}
	if err = tx.Commit(); err != nil {
		return err
	}
	var count int
	if err = pool.QueryRowContext(ctx, "SELECT COUNT(*) FROM benchmark_rows").Scan(&count); err != nil {
		return err
	}
	if count != r.cfg.rows {
		return errors.New("invalid fixture count")
	}
	return nil
}
func (r *runner) regression(db *mariamem.Database, phase string, clients int) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, pool.Close()) }()
	connections := make([]*sql.Conn, 0, clients)
	defer func() {
		for _, conn := range connections {
			conn.Close()
		}
	}()
	for i := 0; i < clients; i++ {
		conn, e := pool.Conn(ctx)
		if e != nil {
			return e
		}
		connections = append(connections, conn)
		if _, e = conn.ExecContext(ctx, "SET @baseline_session = ?", i); e != nil {
			return e
		}
	}
	type result struct {
		rows []map[string]any
		err  error
	}
	out := make(chan result, clients)
	for i, conn := range connections {
		go func(i int, conn *sql.Conn) {
			var session int
			if e := conn.QueryRowContext(ctx, "SELECT @baseline_session").Scan(&session); e != nil || session != i {
				out <- result{err: errors.Join(e, errors.New("session isolation mismatch"))}
				return
			}
			rows := make([]map[string]any, 0, r.cfg.queries)
			for q := 0; q < r.cfg.queries; q++ {
				start := time.Now()
				var value int
				e := conn.QueryRowContext(ctx, "SELECT 1").Scan(&value)
				elapsed := time.Since(start).Seconds()
				if e != nil || value != 1 {
					out <- result{err: errors.Join(e, errors.New("SELECT 1 mismatch"))}
					return
				}
				name := "select_1"
				if clients != 1 {
					name = "multi_connection_select_1"
				}
				rows = append(rows, map[string]any{"case": name, "workers": clients, "phase": phase, "client": i, "query": q, "latency_seconds": elapsed})
			}
			out <- result{rows: rows}
		}(i, conn)
	}
	for range clients {
		value := <-out
		r.samples = append(r.samples, value.rows...)
		err = errors.Join(err, value.err)
	}
	return err
}
func (r *runner) batch(saved *mariamem.Snapshot, workers int) (row map[string]any, err error) {
	monitor, err := newSampler(time.Duration(r.cfg.interval * float64(time.Second)))
	if err != nil {
		return nil, err
	}
	begin := time.Now()
	cpu := selfCPU()
	monitor.start(begin)
	release := make(chan struct{})
	type result struct {
		row map[string]any
		err error
	}
	ready := make(chan result, workers)
	clean := make(chan error, workers)
	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			db, value, e := r.startup(saved, begin)
			ready <- result{value, e}
			if db != nil {
				<-release
				clean <- db.Close()
			}
		}()
	}
	perDB := make([]map[string]any, 0, workers)
	wall := 0.0
	for range workers {
		value := <-ready
		err = errors.Join(err, value.err)
		if value.row != nil {
			perDB = append(perDB, value.row)
			wall = max(wall, value.row["ready_at_seconds"].(float64))
		}
	}
	if err == nil {
		time.Sleep(time.Duration(r.cfg.hold * float64(time.Second)))
	}
	cost := monitor.finish(wall)
	if r.captureMemory {
		for _, value := range perDB {
			value["process_diagnostics"] = processDiagnostics(value)
		}
	}
	cleanup := time.Now()
	close(release)
	wg.Wait()
	close(clean)
	for e := range clean {
		err = errors.Join(err, e)
	}
	var delta, per any
	if nearest, ok := cost["nearest_ready_sample"].(*observation); ok && nearest != nil {
		d := nearest.TreeRSS - monitor.baseline.TreeRSS
		delta = d
		per = float64(d) / float64(workers)
	}
	row = map[string]any{"latency_seconds": wall, "ready_seconds": wall, "per_db": perDB, "hold_seconds": r.cfg.hold, "cleanup_seconds": time.Since(cleanup).Seconds(), "cost": cost, "runner_cpu_seconds": cpuDelta(cpu), "incremental_ready_rss_bytes": delta, "incremental_ready_rss_per_db_bytes": per}
	return row, err
}
func (r *runner) run() error {
	for _, phase := range []string{"warmup", "measurement"} {
		runs := r.cfg.runs
		if phase == "warmup" {
			runs = r.cfg.warmup
		}
		if runs == 0 {
			continue
		}
		for i := 0; i < runs; i++ {
			monitor, err := newSampler(time.Duration(r.cfg.interval * float64(time.Second)))
			if err != nil {
				return err
			}
			cpu := selfCPU()
			begin := time.Now()
			monitor.start(begin)
			db, row, err := r.startup(nil, begin)
			var cost map[string]any
			if db != nil && r.cfg.memoryDiagnostics && phase == "measurement" && i == 0 {
				cost = monitor.finish(row["ready_at_seconds"].(float64))
				row["process_diagnostics"] = processDiagnostics(row)
			}
			if db != nil {
				err = errors.Join(err, db.Close())
			}
			wall := time.Since(begin).Seconds()
			if cost == nil {
				cost = monitor.finish(wall)
			}
			if err != nil {
				return err
			}
			r.version = row["server_version"].(string)
			row["case"] = "start_first_sql"
			row["workers"] = 1
			row["phase"] = phase
			row["run"] = i
			row["wall_seconds"] = wall
			row["runner_cpu_seconds"] = cpuDelta(cpu)
			row["cost"] = cost
			r.samples = append(r.samples, row)
		}
		if err := r.preparedPhase(phase, runs); err != nil {
			return err
		}
	}
	return nil
}
func (r *runner) preparedPhase(phase string, runs int) (err error) {
	var saved *mariamem.Snapshot
	defer func() {
		if saved != nil {
			err = errors.Join(err, saved.Close())
		}
	}()
	for i := 0; i < runs; i++ {
		db, _, e := r.startup(nil, time.Now())
		if e != nil {
			return e
		}
		current, e := func() (*mariamem.Snapshot, error) {
			defer db.Close()
			if e := r.seed(db); e != nil {
				return nil, e
			}
			if i == 0 {
				for _, clients := range []int{1, r.cfg.clients} {
					if e := r.regression(db, phase, clients); e != nil {
						return nil, e
					}
				}
			}
			ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
			defer cancel()
			if e := db.WaitDisconnected(ctx); e != nil {
				return nil, e
			}
			var trace *timing.Trace
			if r.cfg.stages {
				ctx = timing.WithRecorder(ctx, func(t timing.Trace) { trace = &t })
			}
			begin := time.Now()
			snapshot, e := db.Snapshot(ctx, mariamem.SnapshotOptions{})
			elapsed := time.Since(begin).Seconds()
			if e != nil {
				return nil, e
			}
			if !db.Closed() {
				snapshot.Close()
				return nil, errors.New("snapshot source not consumed")
			}
			var stages any
			if r.cfg.stages {
				stages = map[string]any{"host": trace}
			}
			sample := map[string]any{"case": "snapshot", "workers": 1, "phase": phase, "run": i, "latency_seconds": elapsed, "stage_timings": stages, "cpu_seconds": nil, "peak_rss_bytes": nil}
			if r.cfg.initDiagnostics {
				sample["snapshot_inventory"] = snapshotDiagnostics(snapshot.Path())
			}
			r.samples = append(r.samples, sample)
			return snapshot, nil
		}()
		if e != nil {
			return e
		}
		if saved != nil {
			if e = saved.Close(); e != nil {
				current.Close()
				return e
			}
		}
		saved = current
	}
	for _, text := range strings.Split(r.cfg.workers, ",") {
		workers, _ := strconv.Atoi(text)
		for i := 0; i < runs; i++ {
			r.captureMemory = r.cfg.memoryDiagnostics && phase == "measurement" && i == 0
			row, e := r.batch(saved, workers)
			if e != nil {
				return e
			}
			row["case"] = "fork_first_sql"
			row["workers"] = workers
			row["phase"] = phase
			row["run"] = i
			r.samples = append(r.samples, row)
		}
	}
	return nil
}
func main() {
	c := config{}
	flag.StringVar(&c.native, "native-dir", "", "native bundle")
	flag.StringVar(&c.output, "json", "", "raw result path")
	flag.StringVar(&c.workers, "workers", "1,4,8", "concurrency levels")
	flag.IntVar(&c.runs, "runs", 20, "measured runs")
	flag.IntVar(&c.warmup, "warmup", 2, "warmups")
	flag.IntVar(&c.rows, "rows", 1000, "fixture rows")
	flag.IntVar(&c.queries, "queries", 100, "SELECT samples per client")
	flag.IntVar(&c.clients, "clients", 2, "regression clients")
	flag.Float64Var(&c.interval, "interval", .05, "ps sample interval seconds")
	flag.Float64Var(&c.hold, "hold", .1, "post-ready hold seconds")
	flag.BoolVar(&c.stages, "stage-timing", false, "structured stages")
	flag.BoolVar(&c.guestStages, "guest-stage-timing", false, "require matching guest stages")
	flag.BoolVar(&c.initDiagnostics, "init-diagnostics", false, "require detailed initialization diagnostics")
	flag.BoolVar(&c.memoryDiagnostics, "memory-diagnostics", false, "post-ready mapping/thread inventory once per case")
	flag.Parse()
	if c.initDiagnostics || c.memoryDiagnostics {
		c.stages = true
		c.guestStages = true
	}
	if c.initDiagnostics {
		os.Setenv("MARIAMEM_INIT_DIAGNOSTICS", "1")
	} else {
		os.Unsetenv("MARIAMEM_INIT_DIAGNOSTICS")
	}
	if c.native == "" || c.output == "" || c.runs < 1 || c.warmup < 0 || c.rows < 1 || c.queries < 1 || c.clients < 1 || c.interval <= 0 || c.hold < 0 || math.IsNaN(c.interval) || math.IsInf(c.interval, 0) || math.IsNaN(c.hold) || math.IsInf(c.hold, 0) {
		fmt.Fprintln(os.Stderr, "invalid benchmark options")
		os.Exit(2)
	}
	for _, text := range strings.Split(c.workers, ",") {
		n, e := strconv.Atoi(text)
		if e != nil || n < 1 {
			fmt.Fprintln(os.Stderr, "invalid workers")
			os.Exit(2)
		}
	}
	c.stages = c.stages || c.guestStages
	if c.stages {
		directory, e := os.MkdirTemp("", "mariamem-go-timings-")
		if e != nil {
			panic(e)
		}
		defer os.RemoveAll(directory)
		os.Setenv("MARIAMEM_TIMING_DIR", directory)
	}
	r := runner{cfg: c, samples: []map[string]any{}}
	begin := time.Now()
	err := r.run()
	report := map[string]any{"benchmark": "isolation_baseline", "api": "go", "schema_version": 1, "started_at": begin.UTC().Format(time.RFC3339Nano), "completed": err == nil, "samples": r.samples, "environment": map[string]any{"go": runtime.Version(), "goos": runtime.GOOS, "machine": runtime.GOARCH, "cpu_count": runtime.NumCPU(), "server_version": r.version}, "metric_notes": map[string]string{"primary": "Fork to connection and verified first COUNT; group and per-DB wall latency", "cpu": "sampled runtime descendant delta excludes in-process host; runner_cpu_seconds is getrusage SELF over full lifecycle, including host/driver/GC/sampler/hold/cleanup", "rss": "descendant RSS excludes host; process_tree RSS includes Go runner. Incremental RSS subtracts persistent-runner baseline; shared pages may be counted repeatedly", "snapshot_cost": "CPU/RSS unavailable; Snapshot wall time only", "sampling": "ps precision/collection overhead and missing startup/exit edges; informational, no thresholds"}}
	if info, ok := debug.ReadBuildInfo(); ok {
		report["environment"].(map[string]any)["go_build_info"] = info
	}
	if err != nil {
		report["error"] = err.Error()
	}
	data, e := json.MarshalIndent(report, "", "  ")
	if e == nil {
		e = os.MkdirAll(filepath.Dir(c.output), 0755)
	}
	if e == nil {
		e = os.WriteFile(c.output, append(data, '\n'), 0600)
	}
	if err != nil || e != nil {
		fmt.Fprintln(os.Stderr, errors.Join(err, e))
		os.Exit(1)
	}
}
