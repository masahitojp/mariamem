//go:build integration

package godefault

import (
	"context"
	"database/sql"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"os"
	"runtime"
	"testing"
	"time"
)

func TestDefaultNoBundleAndForkIsolation(t *testing.T) {
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	t.Setenv("MARIAMEM_RUNTIME", "")
	cache := t.TempDir()
	t.Setenv("XDG_CACHE_HOME", cache)
	// No Wasmer command is discoverable. Start may use absolute system platform tools.
	t.Setenv("PATH", t.TempDir())
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	conn, err := sql.Open("mysql", db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	for _, q := range []string{"CREATE TABLE fixture(id INT PRIMARY KEY, value INT)", "INSERT INTO fixture VALUES(1,10),(2,20)"} {
		if _, err = conn.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	conn.Close()
	if err = db.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	a, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	ac, _ := sql.Open("mysql", a.DSN())
	defer ac.Close()
	bc, _ := sql.Open("mysql", b.DSN())
	defer bc.Close()
	if _, err = ac.Exec("UPDATE fixture SET value=99 WHERE id=1"); err != nil {
		t.Fatal(err)
	}
	if _, err = ac.Exec("CREATE TABLE private_schema(id INT)"); err != nil {
		t.Fatal(err)
	}
	var value int
	if err = bc.QueryRow("SELECT value FROM fixture WHERE id=1").Scan(&value); err != nil || value != 10 {
		t.Fatalf("isolation: %d %v", value, err)
	}
	if _, err = bc.Exec("SELECT * FROM private_schema"); err == nil {
		t.Fatal("schema leaked")
	}
	if err = a.Close(); err != nil {
		t.Fatal(err)
	}
	if err = bc.QueryRow("SELECT 1").Scan(&value); err != nil || value != 1 {
		t.Fatal(value, err)
	}
	if entries, err := os.ReadDir(cache); err != nil || len(entries) != 0 {
		t.Fatalf("runtime cache unexpectedly used: %v %v", entries, err)
	}
}

// Repeated and concurrent normal lifecycles must not require executable provisioning.
func TestDefaultRepeatedConcurrentLifecycle(t *testing.T) {
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	t.Setenv("MARIAMEM_RUNTIME", "")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	before := runtime.NumGoroutine()
	fdsBefore, _ := os.ReadDir("/dev/fd")
	for round := 0; round < 3; round++ {
		var instances []*mariamem.Database
		for i := 0; i < 2; i++ {
			db, err := mariamem.Start(ctx, mariamem.Options{})
			if err != nil {
				t.Fatal(err)
			}
			instances = append(instances, db)
			t.Cleanup(func() { _ = db.Close() })
			conn, err := sql.Open("mysql", db.DSN())
			if err != nil {
				t.Fatal(err)
			}
			if _, err = conn.Exec("CREATE TABLE independent(id INT PRIMARY KEY)"); err != nil {
				t.Fatal(err)
			}
			if _, err = conn.Exec("INSERT INTO independent VALUES(1)"); err != nil {
				t.Fatal(err)
			}
			conn.Close()
		}
		for _, db := range instances {
			if err := db.Close(); err != nil {
				t.Fatal(err)
			}
			if err := db.Close(); err != nil {
				t.Fatal(err)
			}
		}
	}
	deadline := time.Now().Add(2 * time.Second)
	for runtime.NumGoroutine() > before+8 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if got := runtime.NumGoroutine(); got > before+8 {
		t.Fatalf("retained goroutines: before=%d after=%d", before, got)
	}
	if after, err := os.ReadDir("/dev/fd"); err == nil && len(fdsBefore) > 0 && len(after) > len(fdsBefore)+4 {
		t.Fatalf("retained descriptors: before=%d after=%d", len(fdsBefore), len(after))
	}
}
