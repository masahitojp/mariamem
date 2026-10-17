//go:build integration && ownedroot_probe

package mariamem_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/prepared"
)

func TestOwnedRootCorruptionProbe(t *testing.T) {
	out := os.Getenv("OWNED_ROOT_PROBE_EVIDENCE")
	if out == "" {
		t.Fatal("explicit evidence directory required")
	}
	for _, kind := range []string{"healthy", "corrupt"} {
		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Second)
		cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestOwnedRootCorruptionWorker$", "-test.v")
		cmd.Env = append(os.Environ(), "OWNED_ROOT_PROBE_KIND="+kind)
		raw, e := cmd.CombinedOutput()
		cancel()
		if err := os.WriteFile(filepath.Join(out, kind+".txt"), raw, 0600); err != nil {
			t.Fatal(err)
		}
		if e != nil {
			t.Fatalf("%s process failed: %v; see preserved output", kind, e)
		}
	}
}
func TestOwnedRootCorruptionWorker(t *testing.T) {
	kind := os.Getenv("OWNED_ROOT_PROBE_KIND")
	if kind == "" {
		t.Skip("subprocess only")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 35*time.Second)
	defer cancel()
	result := map[string]any{"kind": kind, "variables": map[string]string{}}
	save := func() {
		p, e := json.MarshalIndent(result, "", "  ")
		if e != nil {
			t.Error(e)
			return
		}
		if e = os.WriteFile(filepath.Join(os.Getenv("OWNED_ROOT_PROBE_EVIDENCE"), kind+".json"), append(p, '\n'), 0600); e != nil {
			t.Error(e)
		}
	}
	defer save()
	opts := mariamem.Options{StartupTimeout: 10 * time.Second, ShutdownTimeout: 5 * time.Second, QueryTimeout: 5 * time.Second}
	db, e := mariamem.Start(ctx, opts)
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close(context.Background())
	pool, e := sql.Open("mysql", db.DSN())
	if e != nil {
		t.Fatal(e)
	}
	token := "owned_root_checksum_payload_" + strings.Repeat("abcdefghjkmnpqrstuvwxyz23456789", 4)
	for _, q := range []string{"CREATE TABLE checksum_probe(id INT PRIMARY KEY,payload VARBINARY(256)) ENGINE=InnoDB ROW_FORMAT=DYNAMIC", "INSERT INTO checksum_probe VALUES(1,'" + token + "')"} {
		if _, e = pool.ExecContext(ctx, q); e != nil {
			t.Fatal(e)
		}
	}
	rows, e := pool.QueryContext(ctx, "SHOW VARIABLES WHERE Variable_name IN ('innodb_checksum_algorithm','innodb_log_checksums','innodb_force_recovery','innodb_doublewrite','innodb_file_per_table','innodb_page_size')")
	if e != nil {
		t.Fatal(e)
	}
	vars := result["variables"].(map[string]string)
	for rows.Next() {
		var k, v string
		if e = rows.Scan(&k, &v); e != nil {
			t.Fatal(e)
		}
		vars[k] = v
	}
	if e = rows.Err(); e != nil {
		t.Fatal(e)
	}
	rows.Close()
	if vars["innodb_page_size"] != "16384" {
		t.Fatalf("probe requires 16KiB page: %v", vars)
	}
	pool.Close()
	if e = db.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	probe := &prepared.RootCorruptionProbe{Mutate: kind == "corrupt", Token: token}
	result["injection"] = probe
	snap, e := db.Snapshot(prepared.WithRootCorruptionProbe(ctx, probe))
	if e != nil {
		result["outcome"] = "capture_error"
		result["error"] = e.Error()
		t.Fatal(e)
	}
	defer snap.Close()
	if probe.File == "" || !probe.MetadataAccepted || probe.StrictRejected != (kind == "corrupt") {
		t.Fatalf("probe oracle mismatch: %+v", probe)
	}
	child, e := snap.Fork(ctx, opts)
	if e != nil {
		result["outcome"] = "startup_error"
		result["error"] = e.Error()
		if kind == "healthy" {
			t.Fatal(e)
		}
		return
	}
	defer child.Close(context.Background())
	p, e := sql.Open("mysql", child.DSN())
	if e != nil {
		t.Fatal(e)
	}
	defer p.Close()
	var got string
	e = p.QueryRowContext(ctx, "SELECT payload FROM checksum_probe WHERE id=1").Scan(&got)
	result["logs"] = child.Logs()
	if e != nil {
		result["outcome"] = "query_error"
		result["error"] = e.Error()
		if kind == "healthy" {
			t.Fatal(e)
		}
		return
	}
	if got == token {
		result["outcome"] = "original_value"
	} else {
		result["outcome"] = "changed_value"
		result["returned_payload"] = got
	}
	if kind == "healthy" && got != token {
		t.Fatal("healthy payload changed")
	}
}
