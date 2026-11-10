//go:build integration

package gointegration_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

func TestShutdownModeSnapshotAndResnapshot(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	db, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	c := openSQLClient(t, ctx, db)
	defer c.Close()
	for _, q := range []string{"CREATE TABLE shutdown_items(id INT PRIMARY KEY, value INT)", "INSERT INTO shutdown_items VALUES(1,42)", "SET GLOBAL innodb_fast_shutdown=2"} {
		if _, e = c.conn.ExecContext(ctx, q); e != nil {
			t.Fatal(e)
		}
	}
	c.Close()
	if e = db.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if e != nil {
		t.Fatal(e)
	}
	defer snap.Close()
	child, e := snap.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer child.Close()
	cc := openSQLClient(t, ctx, child)
	defer cc.Close()
	if got := queryInt(t, ctx, cc, "SELECT value FROM shutdown_items"); got != 42 {
		t.Fatal(got)
	}
	for _, q := range []string{"SET GLOBAL innodb_fast_shutdown=2", "BEGIN", "UPDATE shutdown_items SET value=99"} {
		if _, e = cc.conn.ExecContext(ctx, q); e != nil {
			t.Fatal(e)
		}
	}
	// A Fork child can become a new clean baseline, even after the client
	// selected crash-style shutdown and left a transaction open.
	next, e := child.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: true})
	if e != nil {
		t.Fatal(e)
	}
	defer next.Close()
	cc.Close()
	final, e := next.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer final.Close()
	fc := openSQLClient(t, ctx, final)
	defer fc.Close()
	if got := queryInt(t, ctx, fc, "SELECT value FROM shutdown_items"); got != 42 {
		t.Fatalf("uncommitted value escaped: %d", got)
	}
	if strings.Contains(final.Logs(), "Starting crash recovery") {
		t.Fatal("snapshot required crash recovery")
	}
	// Discard Close must also drain an active transaction/connection and allow
	// repeated disposal, while the original baseline remains independently usable.
	if _, e = fc.conn.ExecContext(ctx, "BEGIN"); e != nil {
		t.Fatal(e)
	}
	if _, e = fc.conn.ExecContext(ctx, "UPDATE shutdown_items SET value=123"); e != nil {
		t.Fatal(e)
	}
	if e = final.Close(); e != nil {
		t.Fatal(e)
	}
	if e = final.Close(); e != nil {
		t.Fatal(e)
	}
	sibling, e := snap.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer sibling.Close()
	sc := openSQLClient(t, ctx, sibling)
	defer sc.Close()
	if got := queryInt(t, ctx, sc, "SELECT value FROM shutdown_items"); got != 42 {
		t.Fatal(got)
	}
}
