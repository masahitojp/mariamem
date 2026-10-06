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
	default:
		panic("unknown mode")
	}
	close(done)
}
