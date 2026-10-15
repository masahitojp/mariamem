package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	mm "github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/prepared"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
)

var ctx = context.Background()

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func assert(v bool, msg string) {
	if !v {
		panic(msg)
	}
}
func connect(db *mm.Database) *sql.DB {
	c, e := sql.Open("mysql", db.DSN())
	must(e)
	c.SetMaxOpenConns(1)
	c.SetMaxIdleConns(1)
	must(c.PingContext(ctx))
	return c
}
func exec(c *sql.DB, q string, args ...any) { _, e := c.ExecContext(ctx, q, args...); must(e) }
func scalar(c *sql.DB, q string) int        { var n int; must(c.QueryRowContext(ctx, q).Scan(&n)); return n }
func disconnect(db *mm.Database, c *sql.DB) { must(c.Close()); must(db.WaitDisconnected(ctx)) }
func start() *mm.Database                   { d, e := mm.Start(ctx, mm.Options{}); must(e); return d }
func snap(d *mm.Database) *mm.Snapshot {
	s, e := d.Snapshot(ctx, mm.SnapshotOptions{})
	must(e)
	return s
}
func fork(s *mm.Snapshot) *mm.Database { d, e := s.Fork(ctx); must(e); return d }
func scratch() map[string]int64 {
	r := map[string]int64{"files": 0, "dirs": 0, "bytes": 0}
	must(filepath.WalkDir(os.TempDir(), func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if p == os.TempDir() {
			return nil
		}
		if d.IsDir() {
			r["dirs"]++
		} else {
			r["files"]++
			s, e := d.Info()
			if e != nil {
				return e
			}
			r["bytes"] += s.Size()
		}
		return nil
	}))
	return r
}
func memory() map[string]uint64 {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return map[string]uint64{"total_alloc": m.TotalAlloc, "heap_alloc": m.HeapAlloc, "heap_sys": m.HeapSys, "num_gc": uint64(m.NumGC), "maxrss_raw": uint64(r.Maxrss)}
}
func workflow(mode string, rows int, resources bool) map[string]any {
	result := map[string]any{"mode": mode, "rows": rows, "guest": "12.3.3", "resources_enabled": resources}
	times := map[string]float64{}
	res := map[string]any{}
	excluded := time.Duration(0)
	timed := func(n string, f func()) {
		at := time.Now()
		f()
		times[n] = float64(time.Since(at).Nanoseconds()) / 1e6
	}
	observe := func(n string) {
		if resources {
			at := time.Now()
			res[n] = memory()
			excluded += time.Since(at)
		}
	}
	begin := time.Now()
	var db *mm.Database
	var baseline *mm.Snapshot
	timed("setup/start", func() { db = start() })
	defer db.Close()
	observe("after-start")
	timed("setup/migrate-seed", func() {
		c := connect(db)
		var version string
		must(c.QueryRow("SELECT VERSION()").Scan(&version))
		assert(strings.HasPrefix(version, "12.3.3"), version)
		exec(c, "CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR(128) NOT NULL UNIQUE, status INT NOT NULL, payload TEXT) ENGINE=InnoDB")
		exec(c, "CREATE TABLE orders (id INT PRIMARY KEY, user_id INT NOT NULL, amount INT NOT NULL, KEY(user_id), FOREIGN KEY(user_id) REFERENCES users(id)) ENGINE=InnoDB")
		payload := strings.Repeat("x", 256)
		if rows > 100 {
			payload = strings.Repeat("x", 1024)
		}
		exec(c, "START TRANSACTION")
		for lo := 1; lo <= rows; lo += 500 {
			hi := min(rows+1, lo+500)
			parts := []string{}
			args := []any{}
			for i := lo; i < hi; i++ {
				parts = append(parts, "(?,?,?,?)")
				args = append(args, i, fmt.Sprintf("u%d@example.test", i), 0, payload)
			}
			exec(c, "INSERT INTO users VALUES "+strings.Join(parts, ","), args...)
		}
		for lo := 1; lo <= rows; lo += 500 {
			hi := min(rows+1, lo+500)
			parts := []string{}
			args := []any{}
			for i := lo; i < hi; i++ {
				parts = append(parts, "(?,?,?)")
				args = append(args, i, i, 10)
			}
			exec(c, "INSERT INTO orders VALUES "+strings.Join(parts, ","), args...)
		}
		exec(c, "COMMIT")
		assert(scalar(c, "SELECT COUNT(*) FROM users") == rows, "seed rows")
		disconnect(db, c)
	})
	observe("after-seed")
	timed("setup/snapshot", func() { baseline = snap(db) })
	defer baseline.Close()
	observe("after-snapshot")
	at := time.Now()
	result["tmp_after_snapshot"] = scratch()
	if mode == "heap" {
		assert(scratch()["files"] == 0, "heap snapshot created files")
		result["heap_stats"] = baseline.ExperimentHeapStats()
	}
	excluded += time.Since(at)
	for _, name := range []string{"first", "second"} {
		var child *mm.Database
		var c *sql.DB
		timed(name+"/startup", func() { child = fork(baseline) })
		defer child.Close()
		observe(name + "-started")
		timed(name+"/connect", func() { c = connect(child) })
		timed(name+"/crud", func() {
			assert(scalar(c, "SELECT COUNT(*) FROM users") == rows, "sibling row count")
			assert(scalar(c, "SELECT status FROM users WHERE id=1") == 0, "sibling initial value")
			exec(c, "START TRANSACTION")
			if name == "first" {
				exec(c, "INSERT INTO users VALUES (?,?,0,?)", rows+1, "created@example.test", "new")
				exec(c, "INSERT INTO orders VALUES (?,?,10)", rows+1, rows+1)
				exec(c, "COMMIT")
				assert(scalar(c, "SELECT COUNT(*) FROM users") == rows+1, "first insert")
			} else {
				assert(scalar(c, "SELECT COUNT(*) FROM users WHERE email='created@example.test'") == 0, "sibling leak")
				exec(c, "UPDATE users SET status=2 WHERE id=1")
				exec(c, "COMMIT")
				assert(scalar(c, "SELECT status FROM users WHERE id=1") == 2, "update")
				exec(c, "START TRANSACTION")
				exec(c, "DELETE FROM orders WHERE id=1")
				exec(c, "ROLLBACK")
				assert(scalar(c, "SELECT COUNT(*) FROM orders") == rows, "rollback")
				exec(c, "START TRANSACTION")
				exec(c, "DELETE FROM orders WHERE id=1")
				exec(c, "COMMIT")
				assert(scalar(c, "SELECT COUNT(*) FROM orders") == rows-1, "delete")
			}
		})
		timed(name+"/disconnect", func() { disconnect(child, c) })
		timed(name+"/close", func() { must(child.Close()) })
		observe(name + "-closed")
	}
	at = time.Now()
	if mode == "heap" {
		must(baseline.ExperimentHeapVerify())
	}
	excluded += time.Since(at)
	timed("baseline/close", func() { must(baseline.Close()) })
	result["whole_ms"] = float64((time.Since(begin) - excluded).Nanoseconds()) / 1e6
	observe("after-close")
	if resources {
		at := time.Now()
		runtime.GC()
		result["post_close_forced_gc_ms"] = float64(time.Since(at).Nanoseconds()) / 1e6
		res["after-close-gc"] = memory()
	}
	result["times_ms"] = times
	result["resources"] = res
	result["tmp_after_close"] = scratch()
	assert(scratch()["files"] == 0 && scratch()["dirs"] == 0, "leftover scratch")
	assert(prepared.HeapRequests() == 0, "request retained")
	result["status"] = "PASS"
	result["checks"] = []string{"version", "seed", "CRUD-commit-rollback", "sibling-isolation", "cleanup"}
	return result
}
func boundaries() map[string]any {
	checks := []string{}
	failures := []map[string]any{}
	db := start()
	c := connect(db)
	exec(c, "CREATE TABLE items(id INT PRIMARY KEY,v INT) ENGINE=InnoDB")
	exec(c, "INSERT INTO items VALUES(1,10)")
	exec(c, "START TRANSACTION")
	exec(c, "UPDATE items SET v=11")
	_, e := db.Snapshot(ctx, mm.SnapshotOptions{})
	assert(errors.Is(e, mm.ErrTransactionActive) && !db.Closed(), "transaction rejected source usable")
	assert(scalar(c, "SELECT v FROM items") == 11, "transaction value")
	exec(c, "ROLLBACK")
	disconnect(db, c)
	checks = append(checks, "transaction-reject-source-usable")
	base := snap(db)
	a := fork(base)
	b := fork(base)
	must(base.Close())
	c = connect(a)
	exec(c, "UPDATE items SET v=20")
	disconnect(a, c)
	c = connect(b)
	assert(scalar(c, "SELECT v FROM items") == 10, "parent close / sibling")
	disconnect(b, c)
	derived := snap(a)
	third := fork(derived)
	must(derived.Close())
	c = connect(third)
	assert(scalar(c, "SELECT v FROM items") == 20, "derived")
	disconnect(third, c)
	must(third.Close())
	c = connect(b)
	assert(scalar(c, "SELECT v FROM items") == 10, "derived sibling")
	disconnect(b, c)
	must(b.Close())
	checks = append(checks, "parent-close-two-live-children", "derived-close-child-survives-sibling-isolates")
	// Real concurrent operations in two independently owned runtimes.
	db = start()
	c = connect(db)
	exec(c, "CREATE TABLE items(id INT PRIMARY KEY,v INT) ENGINE=InnoDB")
	exec(c, "INSERT INTO items VALUES(1,10)")
	disconnect(db, c)
	base = snap(db)
	a = fork(base)
	b = fork(base)
	must(base.Close())
	var wg sync.WaitGroup
	for i, d := range []*mm.Database{a, b} {
		wg.Add(1)
		go func(i int, d *mm.Database) {
			defer wg.Done()
			c := connect(d)
			for j := 0; j < 10; j++ {
				exec(c, "UPDATE items SET v=v+?", i+1)
			}
			assert(scalar(c, "SELECT v FROM items") == 10+10*(i+1), "concurrent isolation")
			disconnect(d, c)
			must(d.Close())
		}(i, d)
	}
	wg.Wait()
	checks = append(checks, "concurrent-independent-children")
	for _, fault := range []string{"freeze", "target_corrupt", "owner_corrupt"} {
		db = start()
		c = connect(db)
		exec(c, "CREATE TABLE items(id INT PRIMARY KEY,v INT) ENGINE=InnoDB")
		exec(c, "INSERT INTO items VALUES(1,10)")
		disconnect(db, c)
		must(os.Setenv("MARIAMEM_HEAP_FAULT", fault))
		s, e := db.Snapshot(ctx, mm.SnapshotOptions{})
		assert(s == nil && e != nil && db.Closed(), "fault accepted")
		want := "heap content mismatch"
		if fault == "freeze" {
			want = "injected heap freeze"
		}
		assert(strings.Contains(e.Error(), want), e.Error())
		failures = append(failures, map[string]any{"fault": fault, "error": e.Error(), "closed": db.Closed()})
		must(os.Unsetenv("MARIAMEM_HEAP_FAULT"))
		_ = db.Close()
	}
	checks = append(checks, "freeze-and-two-corruption-gates-reject")
	assert(prepared.HeapRequests() == 0, "capture leak")
	assert(scratch()["files"] == 0 && scratch()["dirs"] == 0, "temp leak")
	checks = append(checks, "no-payload-files-or-temp-residue")
	return map[string]any{"status": "PASS", "checks": checks, "failures": failures}
}
func main() {
	mode := flag.String("mode", "control", "control/heap")
	rows := flag.Int("rows", 100, "seed count")
	resource := flag.Bool("resources", false, "sample MemStats/rusage")
	boundary := flag.Bool("boundaries", false, "lifecycle checks")
	audit := flag.Bool("audit", false, "compare guest Export in memory")
	output := flag.String("output", "", "JSON output outside scratch")
	flag.Parse()
	assert(*mode == "control" || *mode == "heap", "mode")
	if *mode == "heap" {
		must(os.Setenv("MARIAMEM_HEAP", "1"))
	} else {
		must(os.Unsetenv("MARIAMEM_HEAP"))
	}
	if *audit {
		must(os.Setenv("MARIAMEM_HEAP_AUDIT", "1"))
	}
	assert(scratch()["files"] == 0 && scratch()["dirs"] == 0, "scratch not empty")
	var result map[string]any
	if *boundary {
		assert(*mode == "heap", "boundary mode")
		result = boundaries()
	} else {
		result = workflow(*mode, *rows, *resource)
	}
	data, e := json.MarshalIndent(result, "", "  ")
	must(e)
	if *output != "" {
		must(os.WriteFile(*output, append(data, '\n'), 0600))
	} else {
		fmt.Println(string(data))
	}
}
