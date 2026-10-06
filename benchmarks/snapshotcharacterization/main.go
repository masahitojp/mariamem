// Informational public-API characterization, not a production benchmark gate.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
)

var ctx = context.Background()
var helper, output, mode string
var size, forks, suiteN int
var mutation, traced, scanPayload, initialization bool
var maxPhysical float64
var records []any
var recordMu sync.Mutex

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func emit(v any) {
	recordMu.Lock()
	defer recordMu.Unlock()
	records = append(records, v)
}
func flush() {
	recordMu.Lock()
	defer recordMu.Unlock()
	b, e := json.MarshalIndent(records, "", " ")
	must(e)
	must(os.WriteFile(output, b, 0600))
}

func cpu() float64 {
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}
func cost() map[string]any {
	b, e := exec.Command(helper, strconv.Itoa(os.Getpid())).Output()
	must(e)
	var v map[string]map[string]any
	must(json.Unmarshal(b, &v))
	r := v[strconv.Itoa(os.Getpid())]
	if r["error"] != nil {
		panic(r)
	}
	if r["primary_bytes"].(float64) > maxPhysical*(1<<30) || r["rss_bytes"].(float64) > maxPhysical*(1<<30) {
		panic("resource budget exceeded; stop matrix and inspect partial JSON")
	}
	return r
}
func checkpoint(name string) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	r := cost()
	b, e := exec.Command("ps", "-o", "vsz=", "-p", strconv.Itoa(os.Getpid())).Output()
	must(e)
	v, e := strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64)
	must(e)
	b, e = exec.Command("/usr/sbin/lsof", "-nP", "-a", "-p", strconv.Itoa(os.Getpid()), "-Ff").Output()
	must(e)
	fds := 0
	for _, l := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(l, "f") {
			if _, e := strconv.Atoi(l[1:]); e == nil {
				fds++
			}
		}
	}
	emit(map[string]any{"type": "checkpoint", "name": name, "heap_alloc": m.HeapAlloc, "total_alloc": m.TotalAlloc, "heap_sys": m.HeapSys, "goroutines": runtime.NumGoroutine(), "fds": fds, "virtual_bytes": v * 1024, "os": r})
	flush()
}
func connect(db *mariamem.Database) *sql.DB {
	p, e := sql.Open("mysql", db.DSN())
	must(e)
	p.SetMaxOpenConns(1)
	return p
}
func disconnect(db *mariamem.Database, p *sql.DB) { must(p.Close()); must(db.WaitDisconnected(ctx)) }

// Logical payload is deterministic; actual snapshot bytes are inventoried separately.
func setup(db *mariamem.Database) {
	p := connect(db)
	defer disconnect(db, p)
	_, e := p.ExecContext(ctx, "CREATE TABLE characterization (id INT PRIMARY KEY, payload VARBINARY(1024)) ENGINE=InnoDB")
	must(e)
	rows := size * 1024
	if rows == 0 {
		rows = 1
	}
	payload := strings.Repeat("0123456789abcdef", 64)
	for first := 0; first < rows; first += 128 {
		end := first + 128
		if end > rows {
			end = rows
		}
		values := make([]string, 0, end-first)
		args := make([]any, 0, (end-first)*2)
		for i := first; i < end; i++ {
			values = append(values, "(?,?)")
			args = append(args, i, payload)
		}
		_, e = p.ExecContext(ctx, "INSERT INTO characterization VALUES "+strings.Join(values, ","), args...)
		must(e)
	}
}
func use(db *mariamem.Database, mutate bool) {
	p := connect(db)
	defer disconnect(db, p)
	want := size * 1024
	if want == 0 {
		want = 1
	}
	var n int
	must(p.QueryRowContext(ctx, "SELECT COUNT(*) FROM characterization").Scan(&n))
	if n != want {
		panic(fmt.Sprintf("count %d want %d", n, want))
	}
	if scanPayload {
		var checksum uint64
		must(p.QueryRowContext(ctx, "SELECT SUM(CRC32(payload)) FROM characterization").Scan(&checksum))
		emit(map[string]any{"type": "payload_scan", "crc32_sum": checksum, "rows": want, "logical_bytes": int64(want) * 1024})
	}
	if mutate {
		limit := 8
		if want < limit {
			limit = want
		}
		_, e := p.ExecContext(ctx, "UPDATE characterization SET payload=? WHERE id < ?", strings.Repeat("m", 1024), limit)
		must(e)
	}
}
func inventory(s *mariamem.Snapshot) {
	files := map[string]int64{}
	total := int64(0)
	must(filepath.WalkDir(s.Path(), func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type().IsRegular() {
			i, e := d.Info()
			if e != nil {
				return e
			}
			r, e := filepath.Rel(s.Path(), p)
			if e != nil {
				return e
			}
			files[r] = i.Size()
			total += i.Size()
		}
		return nil
	}))
	emit(map[string]any{"type": "inventory", "logical_payload_bytes": int64(size) * (1 << 20), "snapshot_bytes": total, "files": files})
}
func timed(name string, f func()) float64 {
	c := cpu()
	t := time.Now()
	f()
	seconds := time.Since(t).Seconds()
	emit(map[string]any{"type": "operation", "name": name, "seconds": seconds, "cpu_seconds": cpu() - c})
	return seconds
}
func prepare() *mariamem.Snapshot {
	var db *mariamem.Database
	var e error
	timed("prepare_start", func() { db, e = mariamem.Start(ctx, mariamem.Options{}); must(e) })
	timed("prepare_setup", func() { setup(db) })
	var s *mariamem.Snapshot
	timed("snapshot", func() { s, e = db.Snapshot(ctx, mariamem.SnapshotOptions{}); must(e) })
	must(db.Close())
	inventory(s)
	return s
}
func matrix() {
	s := prepare()
	defer s.Close()
	runtime.GC()
	checkpoint("snapshot_retained_after_gc")
	children := make([]*mariamem.Database, forks)
	var wg sync.WaitGroup
	timed("all_forks_ready_and_used", func() {
		for i := range children {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				timed(fmt.Sprintf("fork_ready_%02d", i), func() { var e error; children[i], e = s.Fork(ctx); must(e) })
				timed(fmt.Sprintf("fork_use_%02d", i), func() { use(children[i], mutation) })
			}(i)
		}
		wg.Wait()
	})
	checkpoint("children_live")
	runtime.GC()
	checkpoint("children_live_after_gc")
	if runtime.GOOS == "darwin" {
		b, e := exec.Command("/usr/bin/vmmap", "-summary", strconv.Itoa(os.Getpid())).CombinedOutput()
		must(os.WriteFile(output+".vmmap", b, 0600))
		emit(map[string]any{"type": "vmmap", "error": fmt.Sprint(e)})
	}
	timed("close_all", func() {
		for _, d := range children {
			must(d.Close())
		}
	})
	children = nil
	checkpoint("children_closed")
	runtime.GC()
	checkpoint("children_closed_after_gc")
	must(s.Close())
	s = nil
	runtime.GC()
	checkpoint("snapshot_closed_after_gc")
}
func suite() {
	// Each measured path owns its full suite (including prepare/snapshot/Close).
	timed("fresh_suite", func() {
		for i := 0; i < suiteN; i++ {
			timed(fmt.Sprintf("fresh_cycle_%02d", i), func() {
				d, e := mariamem.Start(ctx, mariamem.Options{})
				must(e)
				setup(d)
				use(d, true)
				must(d.Close())
			})
		}
	})
	runtime.GC()
	checkpoint("fresh_suite_closed_after_gc")
	timed("fork_suite", func() {
		s := prepare()
		for i := 0; i < suiteN; i++ {
			timed(fmt.Sprintf("fork_cycle_%02d", i), func() { d, e := s.Fork(ctx); must(e); use(d, true); must(d.Close()) })
		}
		must(s.Close())
	})
	runtime.GC()
	checkpoint("fork_suite_closed_after_gc")
}
func main() {
	flag.StringVar(&helper, "helper", "", "compiled benchmarks/tools/process_cost.c")
	flag.StringVar(&output, "out", "", "compact JSON evidence path")
	flag.StringVar(&mode, "mode", "matrix", "matrix or suite")
	flag.IntVar(&size, "payload-mib", 0, "additional SQL payload MiB: 0, 10, 100")
	flag.IntVar(&forks, "forks", 1, "live children: 1,4,8,16")
	flag.IntVar(&suiteN, "suite-n", 4, "suite test count")
	flag.BoolVar(&initialization, "init-diagnostics", false, "enable existing bounded guest initialization diagnostics")
	flag.BoolVar(&scanPayload, "scan-payload", false, "scan all payloads with CRC32 (COUNT otherwise)")
	flag.BoolVar(&mutation, "mutation", false, "update at most eight 1KiB rows per child")
	flag.BoolVar(&traced, "trace", true, "opt-in existing startup traces")
	flag.Float64Var(&maxPhysical, "max-memory-gib", 8, "stop before RSS/physical exceeds budget")
	flag.Parse()
	if output == "" || helper == "" || size < 0 || forks < 1 || suiteN < 1 || maxPhysical <= 0 {
		panic("invalid arguments")
	}
	must(os.MkdirAll(filepath.Dir(output), 0700))
	os.Setenv("MARIAMEM_NATIVE_DIR", "")
	os.Setenv("MARIAMEM_RUNTIME", "")
	if initialization {
		os.Setenv("MARIAMEM_INIT_DIAGNOSTICS", "1")
	} else {
		os.Setenv("MARIAMEM_INIT_DIAGNOSTICS", "")
	}
	if traced {
		dir := output + ".traces"
		must(os.MkdirAll(dir, 0700))
		os.Setenv("MARIAMEM_TIMING_DIR", dir)
		ctx = timing.WithRecorder(ctx, func(t timing.Trace) { emit(map[string]any{"type": "trace", "trace": t}) })
	} else {
		os.Setenv("MARIAMEM_TIMING_DIR", "")
	}
	emit(map[string]any{"type": "environment", "go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "pid": os.Getpid(), "payload_mib": size, "forks": forks, "mutation": mutation, "scan_payload": scanPayload, "mode": mode, "suite_n": suiteN, "trace": traced, "init_diagnostics": initialization, "max_memory_gib": maxPhysical, "gc_policy": "diagnostic checkpoints only; no FreeOSMemory"})
	defer flush()
	checkpoint("baseline")
	// Continuous resource watchdog is separate from timed parent CPU accounting.
	done := make(chan struct{})
	go func() {
		ticker := time.NewTicker(250 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				cost()
			case <-done:
				return
			}
		}
	}()
	switch mode {
	case "matrix":
		matrix()
	case "suite":
		suite()
	case "status":
		statusControl()
	case "firstuse":
		firstuse()
	default:
		panic("unknown mode")
	}
	close(done)
}

func measured(name string, f func()) {
	var before, after syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &before)
	var m0, m1 runtime.MemStats
	runtime.ReadMemStats(&m0)
	os0 := cost()
	timed(name, f)
	syscall.Getrusage(syscall.RUSAGE_SELF, &after)
	runtime.ReadMemStats(&m1)
	os1 := cost()
	emit(map[string]any{"type": "resources", "name": name, "minor_faults": after.Minflt - before.Minflt, "major_faults": after.Majflt - before.Majflt, "allocation_bytes": m1.TotalAlloc - m0.TotalAlloc, "heap_delta": int64(m1.HeapAlloc) - int64(m0.HeapAlloc), "physical_delta": os1["primary_bytes"].(float64) - os0["primary_bytes"].(float64), "rss_delta": os1["rss_bytes"].(float64) - os0["rss_bytes"].(float64)})
}
func query(p *sql.DB, kind string) {
	var n uint64
	q := map[string]string{"select1": "SELECT 1", "pk": "SELECT LENGTH(payload) FROM characterization WHERE id=0", "range": "SELECT SUM(LENGTH(payload)) FROM characterization WHERE id < 8", "count": "SELECT COUNT(*) FROM characterization", "scan": "SELECT SUM(CRC32(payload)) FROM characterization"}[kind]
	must(p.QueryRowContext(ctx, q).Scan(&n))
	if kind == "count" {
		want := size * 1024
		if want == 0 {
			want = 1
		}
		if n != uint64(want) {
			panic("wrong count")
		}
	}
	emit(map[string]any{"type": "query_result", "kind": kind, "value": n})
}
func queryPair(d *mariamem.Database, label, kind string) {
	p := connect(d)
	measured(label+"/connect", func() { must(p.PingContext(ctx)) })
	measured(label+"/first", func() { query(p, kind) })
	measured(label+"/second", func() { query(p, kind) })
	disconnect(d, p)
}
func firstuse() {
	d, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	measured("setup", func() { setup(d) })
	var s *mariamem.Snapshot
	measured("snapshot", func() { s, e = d.Snapshot(ctx, mariamem.SnapshotOptions{}); must(e) })
	must(d.Close())
	inventory(s)
	for _, kind := range []string{"select1", "pk", "range", "count", "scan"} {
		var child *mariamem.Database
		measured("fork/"+kind+"/ready", func() { child, e = s.Fork(ctx); must(e) })
		queryPair(child, "fork/"+kind, kind)
		must(child.Close())
	}
	must(s.Close())
	d, e = mariamem.Start(ctx, mariamem.Options{})
	must(e)
	setup(d)
	for _, kind := range []string{"select1", "pk", "range", "count", "scan"} {
		queryPair(d, "fresh/"+kind, kind)
	}
	must(d.Close())
	// Profiles use separate equivalent preparations, outside latency cells.
	if size == 100 && os.Getenv("FIRSTUSE_PROFILE") == "1" {
		d, e = mariamem.Start(ctx, mariamem.Options{})
		must(e)
		setup(d)
		f, e := os.Create(output + ".snapshot.pprof")
		must(e)
		must(pprof.StartCPUProfile(f))
		s, e = d.Snapshot(ctx, mariamem.SnapshotOptions{})
		must(e)
		pprof.StopCPUProfile()
		must(f.Close())
		must(d.Close())
		child, e := s.Fork(ctx)
		must(e)
		p := connect(child)
		must(p.PingContext(ctx))
		f, e = os.Create(output + ".count.pprof")
		must(e)
		must(pprof.StartCPUProfile(f))
		query(p, "count")
		pprof.StopCPUProfile()
		must(f.Close())
		disconnect(child, p)
		must(child.Close())
		must(s.Close())
	}
}

func status(p *sql.DB, label string) {
	rows, e := p.QueryContext(ctx, "SHOW GLOBAL STATUS WHERE Variable_name IN ('Innodb_buffer_pool_reads','Innodb_buffer_pool_read_requests','Innodb_data_read','Innodb_buffer_pool_pages_data','Innodb_buffer_pool_pages_total')")
	must(e)
	defer rows.Close()
	values := map[string]string{}
	for rows.Next() {
		var k, v string
		must(rows.Scan(&k, &v))
		values[k] = v
	}
	must(rows.Err())
	emit(map[string]any{"type": "innodb_status", "label": label, "values": values})
}
func statusControl() {
	d, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	setup(d)
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(e)
	must(d.Close())
	d, e = s.Fork(ctx)
	must(e)
	p := connect(d)
	must(p.PingContext(ctx))
	rows, e := p.QueryContext(ctx, "SHOW VARIABLES WHERE Variable_name IN ('innodb_buffer_pool_size','innodb_page_size','innodb_read_io_threads','innodb_write_io_threads')")
	must(e)
	vars := map[string]string{}
	for rows.Next() {
		var k, v string
		must(rows.Scan(&k, &v))
		vars[k] = v
	}
	must(rows.Close())
	emit(map[string]any{"type": "innodb_variables", "values": vars})
	rows, e = p.QueryContext(ctx, "EXPLAIN SELECT COUNT(*) FROM characterization")
	must(e)
	cols, e := rows.Columns()
	must(e)
	for rows.Next() {
		values := make([]sql.NullString, len(cols))
		dest := make([]any, len(cols))
		for i := range dest {
			dest[i] = &values[i]
		}
		must(rows.Scan(dest...))
		emit(map[string]any{"type": "count_plan", "columns": cols, "values": values})
	}
	must(rows.Close())
	status(p, "before")
	measured("control/count/first", func() { query(p, "count") })
	status(p, "after_first")
	measured("control/count/second", func() { query(p, "count") })
	status(p, "after_second")
	disconnect(d, p)
	must(d.Close())
	must(s.Close())
}
