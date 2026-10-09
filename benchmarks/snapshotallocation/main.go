// Snapshot allocation diagnostic. GC is after measured boundaries only.
package main

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"strings"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func main() {
	out := flag.String("out", "", "fresh trial output")
	flag.Parse()
	must(os.MkdirAll(*out, 0700))
	must(os.Setenv("MARIAMEM_TIMING_DIR", *out))
	runtime.MemProfileRate = 65536
	traces := []timing.Trace{}
	ctx := timing.WithRecorder(context.Background(), func(t timing.Trace) { traces = append(traces, t) })
	db, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	conn, e := sql.Open("mysql", db.DSN())
	must(e)
	_, e = conn.Exec("CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB")
	must(e)
	args := []any{}
	values := []string{}
	for i := 0; i < 1000; i++ {
		values = append(values, "(?,?)")
		args = append(args, i, strings.Repeat("x", 32))
	}
	_, e = conn.Exec("INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...)
	must(e)
	must(conn.Close())
	must(db.WaitDisconnected(ctx))
	var before, after runtime.MemStats
	snapshotPath := filepath.Join(*out, "prepared")
	runtime.ReadMemStats(&before)
	start := time.Now()
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{Destination: snapshotPath})
	must(e)
	defer func() { must(os.RemoveAll(snapshotPath)) }()
	elapsed := time.Since(start)
	runtime.ReadMemStats(&after)
	// Collection only after all measured boundaries, to settle alloc-space profile epoch.
	runtime.GC()
	f, e := os.Create(filepath.Join(*out, "snapshot.heap"))
	must(e)
	must(pprof.WriteHeapProfile(f))
	must(f.Close())
	inventory := map[string]int64{}
	hashes := map[string]string{}
	var bytes int64
	must(filepath.WalkDir(snapshotPath, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if !d.IsDir() {
			s, e := d.Info()
			if e != nil {
				return e
			}
			inventory[strings.TrimPrefix(p, snapshotPath+"/")] = s.Size()
			bytes += s.Size()
			content, e := os.ReadFile(p)
			if e != nil {
				return e
			}
			hashes[strings.TrimPrefix(p, snapshotPath+"/")] = fmt.Sprintf("%x", sha256.Sum256(content))
		}
		return nil
	}))
	a, e := snap.Fork(ctx)
	must(e)
	b, e := snap.Fork(ctx)
	must(e)
	ac, e := sql.Open("mysql", a.DSN())
	must(e)
	bc, e := sql.Open("mysql", b.DSN())
	must(e)
	var count int
	must(bc.QueryRow("SELECT COUNT(*) FROM benchmark_rows").Scan(&count))
	if count != 1000 {
		panic(count)
	}
	_, e = ac.Exec("UPDATE benchmark_rows SET payload='private' WHERE id=0")
	must(e)
	_, e = ac.Exec("CREATE TABLE private_schema(id INT PRIMARY KEY)")
	must(e)
	tx, e := ac.Begin()
	must(e)
	_, e = tx.Exec("INSERT INTO benchmark_rows VALUES(1001,'rollback')")
	must(e)
	must(tx.Rollback())
	must(ac.QueryRow("SELECT COUNT(*) FROM benchmark_rows").Scan(&count))
	if count != 1000 {
		panic(count)
	}
	var value string
	must(bc.QueryRow("SELECT payload FROM benchmark_rows WHERE id=0").Scan(&value))
	if value != strings.Repeat("x", 32) {
		panic(value)
	}
	if _, e = bc.Exec("SELECT * FROM private_schema"); e == nil {
		panic("schema leak")
	}
	must(ac.Close())
	must(a.Close())
	must(bc.QueryRow("SELECT 1").Scan(&count))
	must(bc.Close())
	must(b.Close())
	for name, want := range hashes {
		content, e := os.ReadFile(filepath.Join(snapshotPath, name))
		must(e)
		if fmt.Sprintf("%x", sha256.Sum256(content)) != want {
			panic("base mutated: " + name)
		}
	}
	// External input validation must reject corruption; an already-owned baseline
	// must remain independent of changes to its published output.
	corrupted := ""
	for name := range inventory {
		if strings.HasSuffix(name, "/test/benchmark_rows.ibd") {
			corrupted = filepath.Join(snapshotPath, name)
		}
	}
	if corrupted == "" {
		panic("fixture data file missing from published inventory")
	}
	file, e := os.OpenFile(corrupted, os.O_RDWR, 0)
	must(e)
	_, e = file.WriteAt([]byte("corrupt"), 0)
	must(e)
	must(file.Close())
	if _, e := stored.Validate(snapshotPath, runtimekind.GuestSHA256); e == nil {
		panic("corrupt external snapshot accepted")
	}
	child, e := snap.Fork(ctx)
	must(e)
	cc, e := sql.Open("mysql", child.DSN())
	must(e)
	must(cc.QueryRow("SELECT COUNT(*) FROM benchmark_rows").Scan(&count))
	if count != 1000 {
		panic("external output changed owned baseline")
	}
	must(cc.Close())
	must(child.Close())
	must(snap.Close())
	must(db.Close())
	report := map[string]any{"go": runtime.Version(), "guest_sha256": runtimekind.GuestSHA256, "mallocs_delta": after.Mallocs - before.Mallocs, "snapshot_ms": float64(elapsed) / float64(time.Millisecond), "total_alloc_delta": after.TotalAlloc - before.TotalAlloc, "heap_before": before.HeapAlloc, "heap_after": after.HeapAlloc, "snapshot_bytes": bytes, "inventory": inventory, "traces": traces, "isolation_pass": true, "corruption_rejected": true, "files_sha256": hashes}
	report["snapshot_mode"] = "explicit diagnostic output plus independent owned backing; acquisition differs from historical temporary Snapshot"
	report["corruption_boundary"] = "external inventory/content validation; subsequent Fork uses owned backing"
	data, e := json.MarshalIndent(report, "", "  ")
	must(e)
	must(os.WriteFile(filepath.Join(*out, "result.json"), data, 0600))
	fmt.Println(string(data))
}
