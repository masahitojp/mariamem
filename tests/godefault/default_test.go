//go:build integration

package godefault

import (
	"context"
	"database/sql"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"os"
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
