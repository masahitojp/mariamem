//go:build integration

package godefault

import (
	"context"
	"database/sql"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"net"
	"os"
	"runtime"
	"runtime/debug"
	"strconv"
	"testing"
	"time"
)

func TestExternalTransactionsAndCleanup(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	scratch := t.TempDir()
	t.Setenv("TMPDIR", scratch)
	info, _ := debug.ReadBuildInfo()
	t.Logf("compiler=%s GOTOOLCHAIN=%s", info.GoVersion, os.Getenv("GOTOOLCHAIN"))
	before := runtime.NumGoroutine()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	pool.SetMaxOpenConns(2)
	if _, err = pool.ExecContext(ctx, "CREATE TABLE compat_tx(id INT PRIMARY KEY, value VARCHAR(32)) ENGINE=InnoDB"); err != nil {
		t.Fatal(err)
	}
	a, err := pool.Conn(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := pool.Conn(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	var aid, bid int
	if err = a.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&aid); err != nil {
		t.Fatal(err)
	}
	if err = b.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&bid); err != nil {
		t.Fatal(err)
	}
	if aid == bid {
		t.Fatal("sessions not distinct")
	}
	tx, err := a.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO compat_tx VALUES(1,?)", "committed"); err != nil {
		tx.Rollback()
		t.Fatal(err)
	}
	if err = tx.Commit(); err != nil {
		t.Fatal(err)
	}
	var count int
	if err = b.QueryRowContext(ctx, "SELECT COUNT(*) FROM compat_tx").Scan(&count); err != nil || count != 1 {
		t.Fatalf("commit visibility count=%d err=%v", count, err)
	}
	tx, err = a.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO compat_tx VALUES(2,?)", "rolled-back"); err != nil {
		tx.Rollback()
		t.Fatal(err)
	}
	if err = tx.Rollback(); err != nil {
		t.Fatal(err)
	}
	if err = b.QueryRowContext(ctx, "SELECT COUNT(*) FROM compat_tx").Scan(&count); err != nil || count != 1 {
		t.Fatalf("rollback count=%d err=%v", count, err)
	}
	a.Close()
	b.Close()
	if err = pool.Close(); err != nil {
		t.Fatal(err)
	}
	if err = db.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	for i := 0; i < 2; i++ {
		child, e := snap.Fork(ctx)
		if e != nil {
			t.Fatal(e)
		}
		defer child.Close()
		p, e := sql.Open("mysql", child.DSN())
		if e != nil {
			t.Fatal(e)
		}
		defer p.Close()
		if e = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM compat_tx").Scan(&count); e != nil || count != 1 {
			t.Fatalf("fork count=%d err=%v", count, e)
		}
		if _, e = p.ExecContext(ctx, "INSERT INTO compat_tx VALUES(3,'child')"); e != nil {
			t.Fatal(e)
		}
		if e = p.Close(); e != nil {
			t.Fatal(e)
		}
		endpoint := net.JoinHostPort(child.ConnectionInfo().Host, strconv.Itoa(child.ConnectionInfo().Port))
		if e = child.Close(); e != nil {
			t.Fatal(e)
		}
		if e = child.Close(); e != nil {
			t.Fatal(e)
		}
		c, e := net.DialTimeout("tcp", endpoint, 100*time.Millisecond)
		if e == nil {
			c.Close()
			t.Fatal("closed endpoint still connects")
		}
	}
	if err = snap.Close(); err != nil {
		t.Fatal(err)
	}
	if err = db.Close(); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(scratch)
	if err != nil || len(entries) != 0 {
		t.Fatalf("temporary residue=%v err=%v", entries, err)
	}
	deadline := time.Now().Add(2 * time.Second)
	for runtime.NumGoroutine() > before+2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	after := runtime.NumGoroutine()
	t.Logf("sessions=%d,%d goroutines before=%d after=%d temporary_entries=%d", aid, bid, before, after, len(entries))
	if after > before+2 {
		t.Fatal("goroutine residue")
	}
}
