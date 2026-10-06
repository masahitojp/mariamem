// Bounded same-harness comparison; no release/performance gate.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
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
	if runtime.GOOS == "linux" {
		entries, e := os.ReadDir("/proc/self/fd")
		must(e)
		return len(entries)
	}
	var limit syscall.Rlimit
	must(syscall.Getrlimit(syscall.RLIMIT_NOFILE, &limit))
	count := 0
	for fd := uint64(0); fd < limit.Cur; fd++ {
		_, _, e := syscall.Syscall(syscall.SYS_FCNTL, uintptr(fd), syscall.F_GETFD, 0)
		if e == 0 {
			count++
		}
	}
	return count
}

func pool(db *mariamem.Database) *sql.DB {
	p, e := sql.Open("mysql", db.DSN())
	must(e)
	p.SetMaxOpenConns(1)
	return p
}
func disconnect(db *mariamem.Database, p *sql.DB) { must(p.Close()); must(db.WaitDisconnected(ctx)) }
func main() {
	payload := flag.Int("payload-mib", 0, "deterministic payload MiB")
	n := flag.Int("forks", 16, "sequential children")
	out := flag.String("out", "", "JSON result")
	label := flag.String("label", "", "exact candidate/baseline label")
	helper := flag.String("helper", "", "existing OS process-counter helper")
	export := flag.String("export", "", "fixture provisioning only: explicit output artifact")
	flag.Parse()
	if *out == "" || *n < 1 {
		panic("out and positive forks required")
	}
	result := map[string]any{"label": *label, "payload_mib": *payload, "forks": *n, "go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "fds_before": fds()}
	operations := []map[string]any{}
	resources := map[string]any{}
	probe := func(name string) {
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
		f()
		operations = append(operations, map[string]any{"name": name, "seconds": time.Since(t).Seconds(), "cpu_seconds": cpu() - c})
	}
	total := time.Now()
	var db *mariamem.Database
	measure("prepare_start", func() { var e error; db, e = mariamem.Start(ctx, mariamem.Options{}); must(e) })
	rows := *payload * 1024
	if rows == 0 {
		rows = 1
	}
	measure("prepare_setup", func() {
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
		disconnect(db, p)
	})
	var saved *mariamem.Snapshot
	measure("snapshot", func() {
		var e error
		saved, e = db.Snapshot(ctx, mariamem.SnapshotOptions{Destination: *export})
		must(e)
	})
	result["fds_snapshot"] = fds()
	result["prepare_seconds"] = time.Since(total).Seconds()
	probe("snapshot")
	for i := 0; i < *n; i++ {
		var child *mariamem.Database
		measure(fmt.Sprintf("fork_ready_%02d", i), func() { var e error; child, e = saved.Fork(ctx); must(e) })
		if i == 0 {
			probe("first_ready")
		}
		var p *sql.DB
		measure(fmt.Sprintf("point_use_%02d", i), func() {
			p = pool(child)
			var value string
			must(p.QueryRow("SELECT payload FROM characterization WHERE id=0").Scan(&value))
			if len(value) != 1024 {
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
		measure(fmt.Sprintf("child_close_%02d", i), func() { disconnect(child, p); must(child.Close()) })
		if i == 0 || i == *n-1 {
			probe(fmt.Sprintf("closed_%02d", i))
		}
		if i == 0 {
			result["suite_n1_seconds"] = time.Since(total).Seconds()
		}
	}
	measure("snapshot_close", func() { must(saved.Close()) })
	runtime.GC()
	result["suite_seconds"] = time.Since(total).Seconds()
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
	result["operations"] = operations
	b, e := json.MarshalIndent(result, "", " ")
	must(e)
	must(os.WriteFile(*out, b, 0600))
}
