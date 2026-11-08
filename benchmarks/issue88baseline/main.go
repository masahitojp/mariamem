// Finite public-API baseline measurement; no runtime changes or timing gates.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"os/exec"
	"runtime"
	"runtime/debug"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func cpu() float64 {
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return float64(r.Utime.Nano()+r.Stime.Nano()) / 1e6
}
func ms(t time.Time) float64 { return float64(time.Since(t)) / 1e6 }
func pool(d *mariamem.Database) *sql.DB {
	c, e := mysql.ParseDSN(d.DSN())
	must(e)
	c.DialFunc = d.DialContext
	co, e := mysql.NewConnector(c)
	must(e)
	p := sql.OpenDB(co)
	p.SetMaxOpenConns(1)
	return p
}
func disconnect(ctx context.Context, d *mariamem.Database, p *sql.DB) {
	must(p.Close())
	must(d.WaitDisconnected(ctx))
}
func settings(p *sql.DB) map[string]int64 {
	out := map[string]int64{}
	for _, n := range []string{"innodb_buffer_pool_size", "innodb_buffer_pool_size_max"} {
		var k string
		var v int64
		must(p.QueryRow("SHOW VARIABLES LIKE ?", n).Scan(&k, &v))
		if v != 16<<20 {
			panic(fmt.Sprint(n, " unexpected ", v))
		}
		out[n] = v
	}
	return out
}
func oracle(p *sql.DB) {
	var n, s, l int
	must(p.QueryRow("SELECT COUNT(*),SUM(id),SUM(OCTET_LENGTH(payload)) FROM benchmark_rows").Scan(&n, &s, &l))
	if n != 1000 || s != 499500 || l != 32000 {
		panic("baseline oracle")
	}
}
func mutate(p *sql.DB) {
	_, e := p.Exec("UPDATE benchmark_rows SET payload='changed' WHERE id=0")
	must(e)
	var s string
	must(p.QueryRow("SELECT payload FROM benchmark_rows WHERE id=0").Scan(&s))
	if s != "changed" {
		panic("update oracle")
	}
}
func probe(helper string) any {
	runtime.GC()
	debug.FreeOSMemory()
	time.Sleep(100 * time.Millisecond)
	b, e := exec.Command(helper, strconv.Itoa(os.Getpid())).Output()
	must(e)
	var v map[string]map[string]any
	must(json.Unmarshal(b, &v))
	row := v[strconv.Itoa(os.Getpid())]
	if row["rss_bytes"] == nil {
		panic(string(b))
	}
	return row
}
func run() error {
	mode := flag.String("mode", "serial", "serial or hold")
	out := flag.String("out", "", "output")
	helper := flag.String("helper", "", "process counter")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	result := map[string]any{"mode": *mode, "go": runtime.Version(), "gomaxprocs": runtime.GOMAXPROCS(0), "transport": "Pipe", "rows": 1000, "payload_bytes": 32, "timing_diagnostics": false}
	start := time.Now()
	d, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	p := pool(d)
	result["settings"] = settings(p)
	_, e = p.Exec("CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARBINARY(64)) ENGINE=InnoDB")
	must(e)
	values := []string{}
	args := []any{}
	for i := 0; i < 1000; i++ {
		values = append(values, "(?,?)")
		args = append(args, i, strings.Repeat("x", 32))
	}
	_, e = p.Exec("INSERT INTO benchmark_rows VALUES "+strings.Join(values, ","), args...)
	must(e)
	oracle(p)
	disconnect(ctx, d, p)
	snap, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 4})
	must(e)
	must(d.Close())
	d = nil
	result["prepare_ms"] = ms(start)
	if *mode == "serial" {
		// One discarded child warms the same process; its costs are retained separately.
		samples := []any{}
		for i := -1; i < 48; i++ {
			t, c := time.Now(), cpu()
			child, e := snap.Fork(ctx)
			must(e)
			wall, consumed := ms(t), cpu()-c
			q := pool(child)
			t = time.Now()
			oracle(q)
			first := ms(t)
			if i == 0 {
				result["child_settings"] = settings(q)
			}
			mutate(q)
			t = time.Now()
			disconnect(ctx, child, q)
			retire := ms(t)
			t = time.Now()
			must(child.Close())
			closeMS := ms(t)
			row := map[string]any{"index": i, "fork_ms": wall, "fork_cpu_ms": consumed, "first_sql_ms": first, "disconnect_ms": retire, "close_ms": closeMS, "oracle": true}
			if i < 0 {
				result["warmup"] = row
			} else {
				samples = append(samples, row)
			}
		}
		result["samples"] = samples
	} else if *mode == "hold" {
		points := map[string]any{"0": probe(*helper)}
		children := []*mariamem.Database{}
		for i := 1; i <= 4; i++ {
			child, e := snap.Fork(ctx)
			must(e)
			children = append(children, child)
			q := pool(child)
			oracle(q)
			disconnect(ctx, child, q)
			if i == 1 || i == 4 {
				points[strconv.Itoa(i)] = probe(*helper)
			}
		}
		for _, child := range children {
			must(child.Close())
		}
		children = nil
		result["rss_points"] = points
	} else {
		return fmt.Errorf("bad mode")
	}
	// A final pristine child proves the baseline survived all committed mutations.
	child, e := snap.Fork(ctx)
	must(e)
	q := pool(child)
	oracle(q)
	disconnect(ctx, child, q)
	must(child.Close())
	must(snap.Close())
	snap = nil
	result["mapping_stats"] = base.MemoryMappingStats()
	if base.MemoryMappingStats()["active_mappings"] != 0 {
		return fmt.Errorf("mapping leak")
	}
	result["success"] = true
	data, e := json.MarshalIndent(result, "", "  ")
	must(e)
	return os.WriteFile(*out, append(data, '\n'), 0600)
}
func main() { must(run()) }
