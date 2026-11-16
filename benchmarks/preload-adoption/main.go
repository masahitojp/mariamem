// Bounded workload control, not a public configuration API.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	mm "github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func elapsed(t time.Time) float64 { return float64(time.Since(t)) / 1e6 }
func cpu() float64 {
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return float64(r.Utime.Nano()+r.Stime.Nano()) / 1e6
}
func conn(d *mm.Database) *sql.DB {
	c, e := mysql.ParseDSN(d.DSN())
	must(e)
	c.DialFunc = d.DialContext
	x, e := mysql.NewConnector(c)
	must(e)
	q := sql.OpenDB(x)
	q.SetMaxOpenConns(1)
	return q
}
func disconnect(ctx context.Context, d *mm.Database, q *sql.DB) {
	must(q.Close())
	must(d.WaitDisconnected(ctx))
}
func settings(q *sql.DB, fresh bool) {
	var load, size, read int
	must(q.QueryRow("SELECT @@global.innodb_buffer_pool_load_at_startup,@@global.innodb_buffer_pool_size,@@global.innodb_read_io_threads").Scan(&load, &size, &read))
	want := 1
	if fresh || os.Getenv("EXPERIMENT_BUFFER_LOAD") == "OFF" {
		want = 0
	}
	if load != want || size != 16<<20 || read != 1 {
		panic(fmt.Sprintf("settings %d %d %d", load, size, read))
	}
}
func oracle(q *sql.DB, n int) {
	var count, sum, length int
	must(q.QueryRow("SELECT COUNT(*),SUM(id),SUM(OCTET_LENGTH(payload)) FROM preload_rows").Scan(&count, &sum, &length))
	if count != n || sum != n*(n-1)/2 || length != n*1024 {
		panic("oracle mismatch")
	}
}
func mutate(q *sql.DB) {
	_, e := q.Exec("UPDATE preload_rows SET payload='changed' WHERE id=0")
	must(e)
	var v string
	must(q.QueryRow("SELECT payload FROM preload_rows WHERE id=0").Scan(&v))
	if v != "changed" {
		panic("mutation mismatch")
	}
}
func main() {
	n := flag.Int("rows", 4096, "rows")
	p := flag.Int("p", 1, "parallel")
	accept := flag.Bool("acceptance", false, "resnapshot check")
	out := flag.String("out", "", "JSON")
	flag.Parse()
	if *p != 1 && *p != 8 {
		panic("parallel")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	start := time.Now()
	c0 := cpu()
	d, e := mm.Start(ctx, mm.Options{})
	must(e)
	q := conn(d)
	settings(q, true)
	_, e = q.Exec("CREATE TABLE preload_rows(id INT PRIMARY KEY,payload VARBINARY(1024)) ENGINE=InnoDB")
	must(e)
	for first := 0; first < *n; first += 256 {
		v := []string{}
		args := []any{}
		for i := first; i < min(first+256, *n); i++ {
			v = append(v, "(?,?)")
			args = append(args, i, strings.Repeat("x", 1024))
		}
		_, e = q.Exec("INSERT INTO preload_rows VALUES "+strings.Join(v, ","), args...)
		must(e)
	}
	rs, e := q.Query("ANALYZE TABLE preload_rows")
	must(e)
	for rs.Next() {
	}
	must(rs.Err())
	must(rs.Close())
	var physical int64
	must(q.QueryRow("SELECT DATA_LENGTH+INDEX_LENGTH FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preload_rows'").Scan(&physical))
	if *n == 24576 && physical <= 16<<20 {
		panic("large fixture too small")
	}
	oracle(q, *n)
	disconnect(ctx, d, q)
	snap, e := d.Snapshot(ctx, mm.SnapshotOptions{MaxForks: *p})
	must(e)
	must(d.Close())
	prepare := elapsed(start)
	rows := make([]map[string]float64, 8)
	batch := time.Now()
	var wg sync.WaitGroup
	jobs := make(chan int)
	for k := 0; k < *p; k++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := range jobs {
				life := time.Now()
				t := time.Now()
				child, e := snap.Fork(ctx)
				must(e)
				fork := elapsed(t)
				q := conn(child)
				t = time.Now()
				oracle(q, *n)
				first := elapsed(t)
				t = time.Now()
				oracle(q, *n)
				second := elapsed(t)
				settings(q, false)
				t = time.Now()
				mutate(q)
				update := elapsed(t)
				t = time.Now()
				disconnect(ctx, child, q)
				must(child.Close())
				closeMS := elapsed(t)
				rows[i] = map[string]float64{"fork_ms": fork, "first_scan_ms": first, "second_scan_ms": second, "update_ms": update, "retire_ms": closeMS, "lifecycle_ms": elapsed(life)}
			}
		}()
	}
	for i := 0; i < 8; i++ {
		jobs <- i
	}
	close(jobs)
	wg.Wait()
	batchMS := elapsed(batch)
	finish := time.Now()
	child, e := snap.Fork(ctx)
	must(e)
	q = conn(child)
	oracle(q, *n)
	settings(q, false)
	if *accept {
		mutate(q)
		disconnect(ctx, child, q)
		nested, e := child.Snapshot(ctx, mm.SnapshotOptions{MaxForks: 1})
		must(e)
		must(child.Close())
		grand, e := nested.Fork(ctx)
		must(e)
		g := conn(grand)
		settings(g, false)
		var payload string
		must(g.QueryRow("SELECT payload FROM preload_rows WHERE id=0").Scan(&payload))
		if payload != "changed" {
			panic("resnapshot lost data")
		}
		var count int
		must(g.QueryRow("SELECT COUNT(*) FROM preload_rows").Scan(&count))
		if count != *n {
			panic("resnapshot count")
		}
		disconnect(ctx, grand, g)
		must(grand.Close())
		must(nested.Close())
	} else {
		disconnect(ctx, child, q)
		must(child.Close())
	}
	must(snap.Close())
	cleanup := elapsed(finish)
	stats := base.MemoryMappingStats()
	if stats["active_mappings"] != 0 {
		panic(fmt.Sprint("mapping leak", stats))
	}
	result := map[string]any{"rows": *n, "parallel": *p, "go": runtime.Version(), "gomaxprocs": runtime.GOMAXPROCS(0), "arm": os.Getenv("EXPERIMENT_BUFFER_LOAD"), "physical_bytes": physical, "prepare_ms": prepare, "batch_ms": batchMS, "final_ms": cleanup, "elapsed_ms": elapsed(start), "cpu_ms": cpu() - c0, "samples": rows, "acceptance": *accept, "mapping_stats": stats, "success": true}
	b, e := json.MarshalIndent(result, "", "  ")
	must(e)
	must(os.WriteFile(*out, b, 0600))
}
