// Explicit candidate acceptance, including allocator counters (not RSS).
package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/host"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func check(ok bool, message string) {
	if !ok {
		panic(message)
	}
}
func connect(port int) *sql.DB {
	db, err := sql.Open("mysql", fmt.Sprintf("root@tcp(127.0.0.1:%d)/test?timeout=10s&readTimeout=30s&multiStatements=true", port))
	must(err)
	db.SetMaxOpenConns(1)
	return db
}
func disconnected(s *host.Server) {
	deadline := time.Now().Add(5 * time.Second)
	for s.Active() != 0 {
		check(time.Now().Before(deadline), "connections not drained")
		time.Sleep(time.Millisecond)
	}
}
func public(ctx context.Context) {
	db, err := mariamem.Start(ctx, mariamem.Options{})
	must(err)
	defer db.Close()
	q, err := sql.Open("mysql", db.DSN())
	must(err)
	_, err = q.Exec("CREATE FUNCTION test.go_value() RETURNS INT DETERMINISTIC RETURN 17")
	must(err)
	_, err = q.Exec("CREATE PROCEDURE test.go_call() BEGIN SELECT test.go_value(); SELECT 18; END")
	must(err)
	rows, err := q.Query("CALL test.go_call()")
	must(err)
	var number int
	check(rows.Next(), "CALL first result missing")
	must(rows.Scan(&number))
	check(number == 17 && !rows.Next() && rows.NextResultSet(), "CALL first result or boundary")
	check(rows.Next(), "CALL second result missing")
	must(rows.Scan(&number))
	check(number == 18 && !rows.Next() && !rows.NextResultSet(), "CALL second result or terminal boundary")
	must(rows.Err())
	must(rows.Close())
	must(q.Close())
	must(db.WaitDisconnected(ctx))
	baseline, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(err)
	defer baseline.Close()
	child, err := baseline.Fork(ctx)
	must(err)
	defer child.Close()
	q, err = sql.Open("mysql", child.DSN())
	must(err)
	defer q.Close()
	stmt, err := q.Prepare("SELECT test.go_value()+?")
	must(err)
	defer stmt.Close()
	var result int
	must(stmt.QueryRow(3).Scan(&result))
	check(result == 20, "prepared routine result")
}
func cleanup(ctx context.Context, mutation string) map[string]any {
	var logs bytes.Buffer
	s, err := host.StartGenerated(ctx, nil, 30*time.Second, &logs)
	must(err)
	defer s.Close(ctx)
	q := connect(s.Port())
	_, err = q.Exec(mutation)
	must(err)
	must(q.Close())
	disconnected(s)
	owned, consumed, err := s.SnapshotHeap(ctx, false)
	must(err)
	check(consumed && owned != nil, "capture not consumed")
	defer owned.Close()
	before := base.MemoryMappingStats()
	dirsBefore, err := filepath.Glob(filepath.Join(os.TempDir(), "mariamem-transfer-*"))
	must(err)
	logs.Reset()
	failed, err := host.StartGenerated(ctx, owned, 30*time.Second, &logs)
	check(err != nil && failed == nil, "incompatible baseline published a server")
	check(strings.Contains(err.Error(), "routine_bootstrap"), "missing actionable bootstrap diagnostic: "+err.Error())
	after := base.MemoryMappingStats()
	for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes", "release_failures"} {
		check(before[key] == after[key], fmt.Sprintf("mapping leak %s: %d -> %d", key, before[key], after[key]))
	}
	check(after["creates"] == before["creates"]+1 && after["releases"] == before["releases"]+1, "failed start did not release exactly one mapping")
	dirsAfter, err2 := filepath.Glob(filepath.Join(os.TempDir(), "mariamem-transfer-*"))
	must(err2)
	check(reflect.DeepEqual(dirsBefore, dirsAfter), "failed start left transfer directories")
	done := make(chan error, 1)
	go func() { done <- owned.Close() }()
	select {
	case err := <-done:
		must(err)
	case <-time.After(5 * time.Second):
		panic("restored snapshot read lease leaked")
	}
	return map[string]any{"mutation": mutation, "result": "PASS", "error": err.Error(), "logs": logs.String(), "before": before, "after": after, "transfer_directories_unchanged": true, "snapshot_close_completed": true}
}
func main() {
	output := flag.String("output", "", "JSON evidence path")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	initial := base.MemoryMappingStats()
	public(ctx)
	var healthyLogs bytes.Buffer
	healthy, err := host.StartGenerated(ctx, nil, 30*time.Second, &healthyLogs)
	must(err)
	healthySQL := connect(healthy.Port())
	var cases []map[string]any
	for _, mutation := range []string{"DROP TABLE mysql.proc", "ALTER TABLE mysql.proc MODIFY comment TEXT COLLATE utf8mb3_bin NULL", "ALTER TABLE mysql.proc DROP PRIMARY KEY, ADD PRIMARY KEY(name,db,type)"} {
		cases = append(cases, cleanup(ctx, mutation))
		var n int
		must(healthySQL.QueryRow("SELECT 19").Scan(&n))
		check(n == 19, "healthy instance failed after rejected start")
	}
	must(healthySQL.Close())
	must(healthy.Close(ctx))
	final := base.MemoryMappingStats()
	for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes", "release_failures"} {
		check(initial[key] == final[key], "overall mapping leak: "+key)
	}
	data, err := json.MarshalIndent(map[string]any{"result": "PASS", "go_prepared_routine": true, "healthy_instance_after_failures": true, "failed_start_cases": cases, "initial": initial, "final": final}, "", "  ")
	must(err)
	if *output != "" {
		must(os.WriteFile(*output, append(data, '\n'), 0644))
	}
	fmt.Println(string(data))
}
