// Same-harness candidate/released-baseline measurement after correctness gates.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/metrics"
	"runtime/pprof"
	"runtime/trace"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

var ctx = context.Background()

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func cpu() float64 {
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}
func fds() int {
	path := "/dev/fd"
	if runtime.GOOS == "linux" {
		path = "/proc/self/fd"
	}
	// /dev/fd entries can disappear while directory entry types are queried.
	// Count names without stat-ing descriptors (including the enumeration FD).
	directory, e := os.Open(path)
	must(e)
	defer directory.Close()
	entries, e := directory.Readdirnames(-1)
	must(e)
	return len(entries)
}

func pool(db *mariamem.Database) *sql.DB {
	p, e := sql.Open("mysql", db.DSN())
	must(e)
	p.SetMaxOpenConns(1)
	return p
}
func disconnect(db *mariamem.Database, p *sql.DB) { must(p.Close()); must(db.WaitDisconnected(ctx)) }
func gcCounters() (float64, uint64) {
	samples := []metrics.Sample{{Name: "/cpu/classes/gc/total:cpu-seconds"}, {Name: "/gc/cycles/total:gc-cycles"}}
	metrics.Read(samples)
	return samples[0].Value.Float64(), samples[1].Value.Uint64()
}
func beginDiagnostic(kind, dir string) func() {
	if kind == "none" {
		return func() {}
	}
	must(os.MkdirAll(dir, 0700))
	file, e := os.Create(filepath.Join(dir, kind+map[string]string{"cpu": ".pprof", "trace": ".trace"}[kind]))
	must(e)
	if kind == "cpu" {
		runtime.SetBlockProfileRate(1)
		old := runtime.SetMutexProfileFraction(1)
		must(pprof.StartCPUProfile(file))
		return func() {
			pprof.StopCPUProfile()
			must(file.Close())
			runtime.SetBlockProfileRate(0)
			runtime.SetMutexProfileFraction(old)
			for _, name := range []string{"block", "mutex"} {
				f, e := os.Create(filepath.Join(dir, name+".pprof"))
				must(e)
				must(pprof.Lookup(name).WriteTo(f, 0))
				must(f.Close())
			}
		}
	}
	must(trace.Start(file))
	return func() { trace.Stop(); must(file.Close()) }
}
func main() {
	payload := flag.Int("payload-mib", 0, "deterministic payload MiB")
	n := flag.Int("forks", 16, "instances")
	lifecycle := flag.String("lifecycle", "fork", "fork or fresh; same fixture/SQL/cleanup")
	workers := flag.Int("workers", 1, "concurrent children (serial phases never compete)")
	workload := flag.String("workload", "read", "read, crud, or app-connections")
	tables := flag.Int("tables", 1, "prepared InnoDB table count")
	fdSnapshots := flag.Int("fd-snapshots", 0, "FD scaling only: retain this many snapshots")
	out := flag.String("out", "", "JSON result")
	label := flag.String("label", "", "exact candidate/baseline label")
	helper := flag.String("helper", "", "existing OS process-counter helper")
	export := flag.String("export", "", "fixture provisioning only: explicit output artifact")
	observeGo := flag.Bool("go-resources", false, "sample Go heap every 25ms and process RSS high-water mark; benchmark only")
	phaseMode := flag.String("phase-mode", "pipeline", "pipeline or barrier")
	procs := flag.Int("procs", 0, "diagnostic GOMAXPROCS override; zero retains native default")
	diagnostic := flag.String("diagnostic", "none", "none, cpu, trace; separate cohort")
	diagnosticDir := flag.String("diagnostic-dir", "", "profile output")
	flag.Parse()
	if *procs < 0 || (*phaseMode != "pipeline" && *phaseMode != "barrier") || (*diagnostic != "none" && *diagnostic != "cpu" && *diagnostic != "trace") || (*diagnostic != "none" && *diagnosticDir == "") {
		panic("invalid study mode")
	}
	if *phaseMode == "barrier" && *workers != *n {
		panic("barrier requires one worker per child")
	}
	if *procs > 0 {
		runtime.GOMAXPROCS(*procs)
	}
	if *export != "" {
		panic("persisted fixture export was removed; prepare an in-memory baseline instead")
	}
	if (*lifecycle != "fork" && *lifecycle != "fresh") || (*lifecycle == "fresh" && (*export != "" || *fdSnapshots != 0)) || *payload < 0 || *out == "" || *n < 1 || *workers < 1 || *tables < 1 || (*workload != "read" && *workload != "crud" && *workload != "app-connections") {
		panic("out and positive forks required")
	}
	result := map[string]any{"label": *label, "payload_mib": *payload, "forks": *n, "go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "fds_before": fds(), "workers": *workers, "workload": *workload, "tables": *tables, "lifecycle": *lifecycle}
	result["phase_mode"], result["diagnostic"], result["requested_procs"] = *phaseMode, *diagnostic, *procs
	result["gomaxprocs"], result["num_cpu"] = runtime.GOMAXPROCS(0), runtime.NumCPU()
	origin := time.Now()
	operations := []map[string]any{}
	var operationsMu sync.Mutex
	resources := map[string]any{}
	var stopGo func() map[string]any
	if *observeGo {
		stopGo = sampleGoResources()
	}
	probe := func(name string) {
		if *observeGo {
			resources[name+"_go"] = goResourcePoint()
		}
		if *helper == "" {
			return
		}
		data, e := exec.Command(*helper, fmt.Sprint(os.Getpid())).Output()
		must(e)
		var counters map[string]any
		must(json.Unmarshal(data, &counters))
		resources[name] = counters[fmt.Sprint(os.Getpid())]
	}
	probe("before")
	measure := func(name string, f func()) {
		t, c := time.Now(), cpu()
		region := trace.StartRegion(ctx, name)
		f()
		region.End()
		ended := time.Now()
		elapsed, consumed := time.Since(t).Seconds(), cpu()-c
		var cpuValue any = consumed
		if *workers > 1 {
			cpuValue = nil
		} // global process CPU overlaps concurrent operations
		operationsMu.Lock()
		operations = append(operations, map[string]any{"name": name, "seconds": elapsed, "cpu_seconds": cpuValue, "begin_ns": t.Sub(origin).Nanoseconds(), "end_ns": ended.Sub(origin).Nanoseconds()})
		operationsMu.Unlock()
	}
	total := time.Now()
	totalCPU := cpu()
	rows := *payload * 1024
	if rows == 0 {
		rows = 1
	}
	prepare := func(db *mariamem.Database) {
		p := pool(db)
		_, e := p.Exec("CREATE TABLE characterization(id INT PRIMARY KEY,payload VARBINARY(1024)) ENGINE=InnoDB")
		must(e)
		data := strings.Repeat("0123456789abcdef", 64)
		for first := 0; first < rows; first += 128 {
			end := first + 128
			if end > rows {
				end = rows
			}
			values := []string{}
			args := []any{}
			for i := first; i < end; i++ {
				values = append(values, "(?,?)")
				args = append(args, i, data)
			}
			_, e = p.Exec("INSERT INTO characterization VALUES "+strings.Join(values, ","), args...)
			must(e)
		}
		for table := 1; table < *tables; table++ {
			_, e = p.Exec(fmt.Sprintf("CREATE TABLE additional_%03d(id INT PRIMARY KEY,value INT) ENGINE=InnoDB", table))
			must(e)
		}
		disconnect(db, p)
	}
	var saved *mariamem.Snapshot
	if *lifecycle == "fork" {
		var db *mariamem.Database
		measure("prepare_start", func() { var e error; db, e = mariamem.Start(ctx, mariamem.Options{}); must(e) })
		measure("prepare_setup", func() { prepare(db) })
		measure("snapshot", func() {
			var e error
			saved, e = db.Snapshot(ctx, mariamem.SnapshotOptions{})
			must(e)
		})
		result["fds_snapshot"] = fds()
		result["prepare_seconds"] = time.Since(total).Seconds()
		probe("snapshot")
	}
	if *fdSnapshots > 0 {
		if *workers != 1 {
			panic("FD scaling is a separate serial resource phase")
		}
		owned := []*mariamem.Snapshot{saved}
		for len(owned) < *fdSnapshots {
			child, e := saved.Fork(ctx)
			if e != nil {
				if !errors.Is(e, syscall.EMFILE) && !errors.Is(e, syscall.ENFILE) {
					panic(e)
				}
				result["fd_limit_error"] = e.Error()
				break
			}
			next, e := child.Snapshot(ctx, mariamem.SnapshotOptions{})
			if e != nil {
				child.Close()
				if !errors.Is(e, syscall.EMFILE) && !errors.Is(e, syscall.ENFILE) {
					panic(e)
				}
				result["fd_limit_error"] = e.Error()
				break
			}
			owned = append(owned, next)
			if len(owned) == 4 || len(owned) == 16 {
				resources[fmt.Sprintf("fds_%d_snapshots", len(owned))] = fds()
			}
		}
		result["fd_snapshots"] = len(owned)
		result["fd_snapshots_requested"] = *fdSnapshots
		result["fds_all_snapshots"] = fds()
		var limit syscall.Rlimit
		must(syscall.Getrlimit(syscall.RLIMIT_NOFILE, &limit))
		result["fd_soft_limit"], result["fd_hard_limit"] = limit.Cur, limit.Max
		probe("all_snapshots")
		for i := len(owned) - 1; i > 0; i-- {
			must(owned[i].Close())
		}
	} else {
		children := make([]*mariamem.Database, *n)
		startChild := func(i int) {
			var child *mariamem.Database
			if *lifecycle == "fresh" {
				measure(fmt.Sprintf("fresh_ready_%02d", i), func() { var e error; child, e = mariamem.Start(ctx, mariamem.Options{}); must(e) })
				measure(fmt.Sprintf("fresh_setup_%02d", i), func() { prepare(child) })
			} else {
				measure(fmt.Sprintf("fork_ready_%02d", i), func() { var e error; child, e = saved.Fork(ctx); must(e) })
			}
			children[i] = child
		}
		useChild := func(i int) {
			child := children[i]
			if i == 0 && *workers == 1 {
				probe("first_ready")
			}
			var p *sql.DB
			measure(fmt.Sprintf("point_use_%02d", i), func() {
				p = pool(child)
				var value string
				must(p.QueryRow("SELECT payload FROM characterization WHERE id=0").Scan(&value))
				if value != strings.Repeat("0123456789abcdef", 64) {
					panic("fixture mismatch")
				}
			})
			measure(fmt.Sprintf("count_use_%02d", i), func() {
				var got int
				must(p.QueryRow("SELECT COUNT(*) FROM characterization").Scan(&got))
				if got != rows {
					panic("row count mismatch")
				}
			})
			if *workload != "read" {
				measure(fmt.Sprintf("mutation_%02d", i), func() {
					// A separate application connection commits normally; the observer
					// connection must see the committed write without a test-wide transaction.
					application := p
					if *workload == "app-connections" {
						application = pool(child)
						defer application.Close()
					}
					tx, e := application.BeginTx(ctx, nil)
					must(e)
					_, e = tx.Exec("INSERT INTO characterization VALUES (?,?)", rows, strings.Repeat("c", 1024))
					must(e)
					_, e = tx.Exec("UPDATE characterization SET payload=? WHERE id=0", strings.Repeat("u", 1024))
					must(e)
					must(tx.Commit())
					var got int
					must(p.QueryRow("SELECT COUNT(*) FROM characterization").Scan(&got))
					if got != rows+1 {
						panic("application commit not visible")
					}
					_, e = application.Exec("DELETE FROM characterization WHERE id=?", rows)
					must(e)
					tx, e = application.BeginTx(ctx, nil)
					must(e)
					_, e = tx.Exec("DELETE FROM characterization WHERE id=0")
					must(e)
					must(tx.Rollback())
					must(p.QueryRow("SELECT COUNT(*) FROM characterization").Scan(&got))
					if got != rows {
						panic("rollback changed state")
					}
				})
			}
			measure(fmt.Sprintf("disconnect_%02d", i), func() { disconnect(child, p) })
			measure(fmt.Sprintf("child_close_%02d", i), func() { must(child.Close()) })
		}
		stopDiagnostic := beginDiagnostic(*diagnostic, *diagnosticDir)
		gcCPU, gcCycles := gcCounters()
		startupCPU := cpu()
		loopBegin := time.Now()
		runChildren(*n, *workers, *phaseMode == "barrier", startChild, useChild, func() {
			end := time.Now()
			result["all_ready_callback_ns"] = end.Sub(origin).Nanoseconds()
			result["gomaxprocs_at_ready"] = runtime.GOMAXPROCS(0)
			result["startup_wall_seconds"] = end.Sub(loopBegin).Seconds()
			result["startup_cpu_seconds"] = cpu() - startupCPU
			endGC, endCycles := gcCounters()
			result["startup_gc_cpu_seconds"] = endGC - gcCPU
			result["startup_gc_cycles"] = endCycles - gcCycles
			stopDiagnostic()
		})
		result["instance_suite_wall_seconds"] = time.Since(loopBegin).Seconds()
		if *lifecycle == "fork" {
			result["fork_suite_wall_seconds"] = result["instance_suite_wall_seconds"]
		}
		probe("children_closed")
	}

	if saved != nil {
		measure("snapshot_close", func() { must(saved.Close()) })
	}
	runtime.GC()
	result["suite_seconds"] = time.Since(total).Seconds()
	result["suite_cpu_seconds"] = cpu() - totalCPU
	result["suite_cpu_scope"] = "RUSAGE_SELF; benchmark/diagnostic overhead included; counter-helper child CPU excluded"
	result["parallel_resource_sampling"] = "before/after child loop only; no simultaneous-child peak sample"
	result["fds_after"] = fds()
	probe("after")
	result["resources"] = resources
	// Suite cost excludes counter-probe subprocesses and FD enumeration. It
	// includes actual preparation, SQL use and cleanup; retain wall time above.
	var sum float64
	for _, op := range operations {
		sum += op["seconds"].(float64)
	}
	result["suite_operation_seconds"] = sum
	var preparation, closing float64
	for _, op := range operations {
		switch op["name"] {
		case "prepare_start", "prepare_setup", "snapshot":
			preparation += op["seconds"].(float64)
		case "snapshot_close":
			closing += op["seconds"].(float64)
		}
	}
	product := sum
	if *workers > 1 {
		product = preparation + result["instance_suite_wall_seconds"].(float64) + closing
	}
	result["suite_product_seconds"] = product
	result["diagnostic_overhead_seconds"] = result["suite_seconds"].(float64) - product
	result["sum_of_operation_seconds"] = sum // overlaps when workers > 1
	result["operations"] = operations
	if stopGo != nil {
		result["go_resource_observation"] = stopGo()
	}
	b, e := json.MarshalIndent(result, "", " ")
	must(e)
	must(os.WriteFile(*out, b, 0600))
}
