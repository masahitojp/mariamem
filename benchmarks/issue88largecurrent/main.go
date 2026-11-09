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

var rows = 1000
var payloadBytes = 32
var count = 48
var expectedMiB = 16

func settings(p *sql.DB) map[string]int64 {
	out := map[string]int64{}
	for _, n := range []string{"innodb_buffer_pool_size", "innodb_buffer_pool_size_max"} {
		var k string
		var v int64
		must(p.QueryRow("SHOW VARIABLES LIKE ?", n).Scan(&k, &v))
		if v != int64(expectedMiB)<<20 {
			panic(fmt.Sprint(n, " unexpected ", v))
		}
		out[n] = v
	}
	return out
}
func oracle(p *sql.DB) {
	var n, s, l int
	must(p.QueryRow("SELECT COUNT(*),SUM(id),SUM(OCTET_LENGTH(payload)) FROM benchmark_rows").Scan(&n, &s, &l))
	if n != rows || s != rows*(rows-1)/2 || l != rows*payloadBytes {
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
	fixture := flag.String("fixture", "small", "small or over-pool-size")
	flag.Parse()
	if os.Getenv("ISSUE88_POOL_MIB") == "8" {
		expectedMiB = 8
	}
	if *fixture == "large" {
		rows = 24576
		payloadBytes = 1024
		count = 8
	} else if *fixture != "small" {
		panic("bad fixture")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	result := map[string]any{"mode": *mode, "go": runtime.Version(), "gomaxprocs": runtime.GOMAXPROCS(0), "transport": "Pipe", "rows": rows, "payload_bytes": payloadBytes, "fixture": *fixture, "requested_pool_mib": expectedMiB, "timing_diagnostics": false}
	start := time.Now()
	processCPU := cpu()
	d, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	p := pool(d)
	result["settings"] = settings(p)
	var readKey string
	var readThreads int
	must(p.QueryRow("SHOW VARIABLES LIKE 'innodb_read_io_threads'").Scan(&readKey, &readThreads))
	if readThreads != 1 {
		panic("unexpected read group")
	}
	result["read_threads"] = readThreads
	_, e = p.Exec("CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARBINARY(1024)) ENGINE=InnoDB")
	must(e)
	for first := 0; first < rows; first += 256 {
		values := []string{}
		args := []any{}
		end := min(first+256, rows)
		for i := first; i < end; i++ {
			values = append(values, "(?,?)")
			args = append(args, i, strings.Repeat("x", payloadBytes))
		}
		_, e = p.Exec("INSERT INTO benchmark_rows VALUES "+strings.Join(values, ","), args...)
		must(e)
	}
	if *fixture == "large" {
		rs, er := p.Query("ANALYZE TABLE benchmark_rows")
		must(er)
		for rs.Next() {
		}
		must(rs.Err())
		must(rs.Close())
	}
	var physical int64
	must(p.QueryRow("SELECT DATA_LENGTH+INDEX_LENGTH FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='benchmark_rows'").Scan(&physical))
	result["table_allocated_bytes"] = physical
	if *fixture == "large" && physical <= 16<<20 {
		panic("fixture not larger than either pool")
	}
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
		for i := -1; i < count; i++ {
			life := time.Now()
			t, c := time.Now(), cpu()
			child, e := snap.Fork(ctx)
			must(e)
			wall, consumed := ms(t), cpu()-c
			q := pool(child)
			t = time.Now()
			oracle(q)
			first := ms(t)
			t = time.Now()
			oracle(q)
			second := ms(t)
			if i == 0 {
				result["child_settings"] = settings(q)
			}
			t = time.Now()
			mutate(q)
			updateMS := ms(t)
			t = time.Now()
			disconnect(ctx, child, q)
			retire := ms(t)
			t = time.Now()
			must(child.Close())
			closeMS := ms(t)
			row := map[string]any{"lifecycle_ms": ms(life), "index": i, "fork_ms": wall, "fork_cpu_ms": consumed, "first_sql_ms": first, "second_scan_ms": second, "update_ms": updateMS, "disconnect_ms": retire, "close_ms": closeMS, "oracle": true}
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
	result["whole_process_ms"] = ms(start)
	result["whole_process_cpu_ms"] = cpu() - processCPU
	result["success"] = true
	data, e := json.MarshalIndent(result, "", "  ")
	must(e)
	return os.WriteFile(*out, append(data, '\n'), 0600)
}
func main() { must(run()) }
