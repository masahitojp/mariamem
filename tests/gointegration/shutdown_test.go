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

func TestShutdownModeRejectedSnapshotPreservesOriginalSetting(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	c := openSQLClient(t, ctx, db)
	defer c.Close()
	for _, q := range []string{
		"CREATE TABLE rej_shutdown(id INT PRIMARY KEY) ENGINE=InnoDB",
		"SET GLOBAL innodb_fast_shutdown=2",
		"BEGIN",
		"INSERT INTO rej_shutdown VALUES(1)",
	} {
		if _, err := c.conn.ExecContext(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := db.Snapshot(ctx, mariamem.SnapshotOptions{}); err == nil {
		t.Fatal("expected Snapshot to be rejected while transaction is active")
	}
	// Rejected Snapshot must preserve the client's innodb_fast_shutdown=2.
	if got := queryInt(t, ctx, c, "SELECT @@GLOBAL.innodb_fast_shutdown"); got != 2 {
		t.Fatalf("rejected Snapshot mutated @@GLOBAL.innodb_fast_shutdown: want 2, got %d", got)
	}
}

func TestShutdownModeFullCapacity16ConnectionsSnapshotAndClose(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()

	// 1. Full 16-connection Snapshot forces innodb_fast_shutdown=1 after worker join.
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	conns := make([]*sqlClient, 0, 16)
	for i := 0; i < 16; i++ {
		c := openSQLClient(t, ctx, db)
		conns = append(conns, c)
	}
	for _, q := range []string{
		"CREATE TABLE full16(id INT PRIMARY KEY) ENGINE=InnoDB",
		"INSERT INTO full16 VALUES(1),(2)",
		"SET GLOBAL innodb_fast_shutdown=2",
	} {
		if _, err := conns[0].conn.ExecContext(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatalf("full-capacity 16-connection Snapshot failed: %v", err)
	}
	defer snap.Close()
	for _, c := range conns {
		c.Close()
	}
	if !strings.Contains(db.Logs(), "NATIVE_STOP mode=capture fast_shutdown=1 mode_applied=1 mode_err=0") {
		t.Fatalf("expected Snapshot to apply fast_shutdown=1 at shutdown boundary, logs:\n%s", db.Logs())
	}
	child, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer child.Close()
	if strings.Contains(child.Logs(), "Starting crash recovery") {
		t.Fatalf("full-capacity Snapshot required crash recovery:\n%s", child.Logs())
	}
	cc := openSQLClient(t, ctx, child)
	if got := queryInt(t, ctx, cc, "SELECT COUNT(*) FROM full16"); got != 2 {
		t.Fatalf("expected 2 restored rows, got %d", got)
	}
	cc.Close()

	// 2. Full 16-connection ordinary discard Close forces innodb_fast_shutdown=2 even if client set 0.
	discard, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	dconns := make([]*sqlClient, 0, 16)
	for i := 0; i < 16; i++ {
		dconns = append(dconns, openSQLClient(t, ctx, discard))
	}
	if _, err := dconns[0].conn.ExecContext(ctx, "SET GLOBAL innodb_fast_shutdown=0"); err != nil {
		t.Fatal(err)
	}
	if err := discard.Close(); err != nil {
		t.Fatalf("full-capacity 16-connection Close failed: %v", err)
	}
	for _, c := range dconns {
		c.Close()
	}
	if !strings.Contains(discard.Logs(), "NATIVE_STOP mode=ordinary fast_shutdown=2 mode_applied=1 mode_err=0") {
		t.Fatalf("expected ordinary Close to apply fast_shutdown=2 at shutdown boundary, logs:\n%s", discard.Logs())
	}
}
