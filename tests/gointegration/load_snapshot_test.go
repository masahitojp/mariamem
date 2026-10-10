//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestLoadSnapshotPersistedLifecycle(t *testing.T) {
	if os.Getenv("MARIAMEM_TEST_DEFAULT") != "1" {
		t.Skip("set MARIAMEM_TEST_DEFAULT=1")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	setup, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer setup.Close()
	pool, err := sql.Open("mysql", setup.DSN())
	if err != nil {
		t.Fatal(err)
	}
	if _, err = pool.ExecContext(ctx, "CREATE TABLE persisted(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
		pool.Close()
		t.Fatal(err)
	}
	if _, err = pool.ExecContext(ctx, "INSERT INTO persisted VALUES(1)"); err != nil {
		pool.Close()
		t.Fatal(err)
	}
	if err = pool.Close(); err != nil {
		t.Fatal(err)
	}
	if err = setup.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "baseline")
	saved, err := setup.Snapshot(ctx, mariamem.SnapshotOptions{Destination: path})
	if err != nil {
		t.Fatal(err)
	}
	if err = saved.Close(); err != nil {
		t.Fatal(err)
	}
	baseline, err := mariamem.LoadSnapshot(ctx, path, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer baseline.Close()
	if err = os.RemoveAll(path); err != nil {
		t.Fatal(err)
	}
	first, err := baseline.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer first.Close()
	second, err := baseline.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	if err = baseline.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err = baseline.Fork(ctx); !errors.Is(err, mariamem.ErrClosed) {
		t.Fatalf("closed parent: %v", err)
	}
	a, err := sql.Open("mysql", first.DSN())
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := sql.Open("mysql", second.DSN())
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	tx, err := a.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO persisted VALUES(2)"); err != nil {
		tx.Rollback()
		t.Fatal(err)
	}
	if err = tx.Commit(); err != nil {
		t.Fatal(err)
	}
	tx, err = a.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO persisted VALUES(3)"); err != nil {
		tx.Rollback()
		t.Fatal(err)
	}
	if err = tx.Rollback(); err != nil {
		t.Fatal(err)
	}
	for _, check := range []struct {
		p    *sql.DB
		want int
	}{{a, 2}, {b, 1}} {
		var n int
		if err = check.p.QueryRowContext(ctx, "SELECT COUNT(*) FROM persisted").Scan(&n); err != nil || n != check.want {
			t.Fatalf("child isolation/transaction: %d want %d: %v", n, check.want, err)
		}
	}
}
