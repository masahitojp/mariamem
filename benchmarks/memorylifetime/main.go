// Disposable diagnostic: public API only; GC/scavenging never enters production.
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
	"runtime/debug"
	"runtime/pprof"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
)

var out, helper string
var vmMaps, liveGC bool
var ctx context.Context

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func checkpoint(name string, snap *mariamem.Snapshot) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	b, e := exec.Command(helper, strconv.Itoa(os.Getpid())).Output()
	must(e)
	var counters any
	must(json.Unmarshal(b, &counters))
	fd, e := exec.Command("/usr/sbin/lsof", "-nP", "-a", "-p", strconv.Itoa(os.Getpid()), "-Fftn").Output()
	must(os.WriteFile(filepath.Join(out, name+".fds.txt"), fd, 0600))
	fds := 0
	for _, line := range strings.Split(string(fd), "\n") {
		if len(line) > 1 && line[0] == 'f' {
			if _, e := strconv.Atoi(line[1:]); e == nil {
				fds++
			}
		}
	}
	bytes, files := int64(0), 0
	inventory := map[string]int64{}
	if snap != nil {
		must(filepath.WalkDir(snap.Path(), func(p string, d os.DirEntry, e error) error {
			if e != nil {
				return e
			}
			if !d.IsDir() {
				s, e := d.Info()
				if e != nil {
					return e
				}
				bytes += s.Size()
				inventory[strings.TrimPrefix(p, snap.Path()+"/")] = s.Size()
				files++
			}
			return nil
		}))
	}
	row := map[string]any{"name": name, "timestamp": time.Now().UTC(), "memstats": m, "os": counters, "goroutines": runtime.NumGoroutine(), "fds": fds, "fd_error": fmt.Sprint(e), "snapshot_bytes": bytes, "snapshot_files": files, "snapshot_inventory": inventory}
	data, e := json.MarshalIndent(row, "", "  ")
	must(e)
	must(os.WriteFile(filepath.Join(out, name+".json"), data, 0600))
	f, e := os.Create(filepath.Join(out, name+".heap"))
	must(e)
	must(pprof.WriteHeapProfile(f))
	must(f.Close())
	// These views are sampled after the numeric checkpoint, not simultaneous.
	if vmMaps {
		v, e := exec.Command("/usr/bin/footprint", "-w", "--swapped", "-p", strconv.Itoa(os.Getpid())).CombinedOutput()
		if e != nil {
			v = append(v, []byte(e.Error())...)
		}
		must(os.WriteFile(filepath.Join(out, name+".footprint.txt"), v, 0600))
		for _, arg := range []string{"-summary", "-summary -pages"} {
			args := strings.Fields(arg)
			args = append(args, strconv.Itoa(os.Getpid()))
			v, e := exec.Command("/usr/bin/vmmap", args...).CombinedOutput()
			suffix := strings.ReplaceAll(arg, " ", "_")
			if e != nil {
				v = append(v, []byte("\n"+e.Error())...)
			}
			must(os.WriteFile(filepath.Join(out, name+suffix+".vmmap"), v, 0600))
		}
	}
	fmt.Println(name)
}
func query(db *mariamem.Database, fixture bool) {
	p, e := sql.Open("mysql", db.DSN())
	must(e)
	if fixture {
		_, e = p.ExecContext(ctx, "CREATE TABLE benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB")
		must(e)
		tx, e := p.BeginTx(ctx, nil)
		must(e)
		v := []string{}
		args := []any{}
		for i := 0; i < 1000; i++ {
			v = append(v, "(?,?)")
			args = append(args, i, strings.Repeat("x", 32))
		}
		_, e = tx.ExecContext(ctx, "INSERT INTO benchmark_rows VALUES"+strings.Join(v, ","), args...)
		must(e)
		must(tx.Commit())
	}
	q, want := "SELECT 1", 1
	if !fixture && db != nil && isFork {
		q, want = "SELECT COUNT(*) FROM benchmark_rows", 1000
	}
	var n int
	must(p.QueryRowContext(ctx, q).Scan(&n))
	if n != want {
		panic(n)
	}
	must(p.Close())
	must(db.WaitDisconnected(ctx))
}

var isFork bool

func prepare() *mariamem.Snapshot {
	db, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	checkpoint("base_ready", nil)
	query(db, true)
	checkpoint("fixture_disconnected", nil)
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(e)
	// API returns only after export, guest join, publication and hash validation.
	checkpoint("snapshot_published_source_handle_retained", snap)
	must(db.Close())
	checkpoint("source_close", snap)
	runtime.KeepAlive(db)
	db = nil
	checkpoint("G0_only_snapshot", snap)
	return snap
}
func collect(prefix string, snap *mariamem.Snapshot) {
	runtime.GC()
	checkpoint(prefix+"_gc", snap)
	debug.FreeOSMemory()
	checkpoint(prefix+"_free", snap)
}
func main() {
	mode := flag.String("scenario", "fresh", "fresh, snapshot, forks, heap")
	n := flag.Int("workers", 1, "fork children")
	flag.BoolVar(&liveGC, "live-gc", false, "extra control: GC with live children, for current inuse profiles")
	flag.BoolVar(&vmMaps, "vmmap", false, "optional separate VM-mapping observations; disabled in controls")
	flag.StringVar(&out, "out", "", "external ignored work directory")
	flag.StringVar(&helper, "helper", "", "canonical process_cost executable")
	flag.Parse()
	if out == "" || helper == "" {
		panic("out/helper required")
	}
	must(os.MkdirAll(out, 0700))
	runtime.MemProfileRate = 64 * 1024 // explicit diagnostic sampling; no generated/runtime changes
	os.Setenv("MARIAMEM_TIMING_DIR", out)
	ctx = context.Background()
	ctx = timing.WithRecorder(ctx, func(t timing.Trace) {
		b, e := json.Marshal(t)
		must(e)
		must(os.WriteFile(filepath.Join(out, "trace-"+t.Operation+"-"+strconv.FormatInt(time.Now().UnixNano(), 10)+".json"), b, 0600))
	})
	info := map[string]any{"scenario": *mode, "workers": *n, "go": runtime.Version(), "pid": os.Getpid(), "runtime": "direct-linked generated-Go", "profile_rate": runtime.MemProfileRate, "vmmap": vmMaps, "live_gc": liveGC}
	b, e := json.Marshal(info)
	must(e)
	must(os.WriteFile(filepath.Join(out, "environment.json"), b, 0600))
	checkpoint("baseline", nil)
	if *mode == "heap" {
		heapControl()
		return
	}
	if *mode == "fresh" {
		db, e := mariamem.Start(ctx, mariamem.Options{})
		must(e)
		checkpoint("ready", nil)
		if liveGC {
			collect("live_instance", nil)
		}
		query(db, false)
		checkpoint("first_sql_disconnected", nil)
		must(db.Close())
		checkpoint("closed_handle_retained", nil)
		collect("closed_handle_retained", nil)
		runtime.KeepAlive(db)
		db = nil
		collect("handle_released", nil)
		return
	}
	snap := prepare()
	if *mode == "snapshot" {
		collect("snapshot_retained", snap)
		must(snap.Close())
		snap = nil
		checkpoint("snapshot_released", nil)
		collect("released", nil)
		return
	}
	if *mode != "forks" {
		panic("unknown scenario")
	}
	isFork = true
	children := make([]*mariamem.Database, *n)
	var wg sync.WaitGroup
	for i := range children {
		wg.Add(1)
		go func() { defer wg.Done(); db, e := snap.Fork(ctx); must(e); query(db, false); children[i] = db }()
	}
	wg.Wait()
	checkpoint("all_ready", snap)
	if liveGC {
		collect("live_children", snap)
	}
	for _, db := range children {
		must(db.Close())
	}
	checkpoint("all_closed_handles_retained", snap)
	collect("closed_handles_retained", snap)
	runtime.KeepAlive(children)
	children = nil
	collect("closed_handles_released", snap)
	must(snap.Close())
	snap = nil
	checkpoint("snapshot_released", nil)
	collect("released", nil)
}

// Same Go allocator as the guest; no database, mappings, or WASIX objects.
func heapControl() {
	b := make([]byte, 2<<30)
	for i := 0; i < 128<<20; i += 4096 {
		b[i] = 1
	}
	checkpoint("heap_touched", nil)
	runtime.KeepAlive(b)
	b = nil
	collect("heap_dead", nil)
	b = make([]byte, 2<<30)
	checkpoint("heap_reused", nil)
	runtime.KeepAlive(b)
	b = nil
	collect("heap_reused_dead", nil)
}
