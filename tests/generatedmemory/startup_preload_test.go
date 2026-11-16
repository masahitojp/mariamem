//go:build integration

package godefault

import (
	"context"
	"database/sql"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"testing"
	"time"
)

// Exercise the effective engine setting, including a captured filesystem and
// reSnapshot, rather than merely asserting the host's configuration text.
func TestStartupPreloadDisabledAcrossSnapshots(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	root, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer root.Close()
	connect := func(d *mariamem.Database) *sql.DB {
		t.Helper()
		cfg, err := mysql.ParseDSN(d.DSN())
		if err != nil {
			t.Fatal(err)
		}
		cfg.DialFunc = d.DialContext
		c, err := mysql.NewConnector(cfg)
		if err != nil {
			t.Fatal(err)
		}
		q := sql.OpenDB(c)
		return q
	}
	check := func(q *sql.DB) {
		t.Helper()
		var load, size int
		if err := q.QueryRowContext(ctx, "SELECT @@global.innodb_buffer_pool_load_at_startup,@@global.innodb_buffer_pool_size").Scan(&load, &size); err != nil {
			t.Fatal(err)
		}
		if load != 0 || size != 16<<20 {
			t.Fatalf("load=%d size=%d", load, size)
		}
	}
	retire := func(d *mariamem.Database, q *sql.DB) {
		t.Helper()
		if err := q.Close(); err != nil {
			t.Fatal(err)
		}
		if err := d.WaitDisconnected(ctx); err != nil {
			t.Fatal(err)
		}
	}
	q := connect(root)
	check(q)
	if _, err := q.ExecContext(ctx, "CREATE TABLE preload_test(id INT PRIMARY KEY)"); err != nil {
		t.Fatal(err)
	}
	retire(root, q)
	snap, err := root.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	child, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer child.Close()
	q = connect(child)
	check(q)
	if _, err := q.ExecContext(ctx, "INSERT INTO preload_test VALUES (1)"); err != nil {
		t.Fatal(err)
	}
	retire(child, q)
	nested, err := child.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	defer nested.Close()
	grand, err := nested.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer grand.Close()
	g := connect(grand)
	check(g)
	var n int
	if err := g.QueryRowContext(ctx, "SELECT COUNT(*) FROM preload_test").Scan(&n); err != nil || n != 1 {
		t.Fatalf("nested count=%d err=%v", n, err)
	}
	retire(grand, g)
	if err := grand.Close(); err != nil {
		t.Fatal(err)
	}
	sibling, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer sibling.Close()
	q = connect(sibling)
	check(q)
	if err := q.QueryRowContext(ctx, "SELECT COUNT(*) FROM preload_test").Scan(&n); err != nil || n != 0 {
		t.Fatalf("sibling count=%d err=%v", n, err)
	}
	retire(sibling, q)
}
