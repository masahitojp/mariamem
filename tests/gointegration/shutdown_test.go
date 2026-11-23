//go:build integration

package gointegration_test

import (
	"context"
	"encoding/json"
	"net"
	"os"
	"path/filepath"
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

// P1-7 actual-guest regression: owner Close while a client is mid-response
// (stalled reading a >64 KiB result) must NOT poison the guest as a client
// output disconnect; Close must succeed and apply innodb_fast_shutdown=2.
func TestShutdownModeOwnerCloseMidResponseAppliesMode2(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	// Seed a >128 KiB result set so response flush blocks when client stops reading.
	setup := openSQLClient(t, ctx, db)
	for _, q := range []string{
		"CREATE TABLE big_close(id INT PRIMARY KEY, body LONGTEXT) ENGINE=InnoDB",
		"INSERT INTO big_close VALUES (1, REPEAT('x', 131072)), (2, REPEAT('y', 131072))",
	} {
		if _, err := setup.conn.ExecContext(ctx, q); err != nil {
			setup.Close()
			t.Fatal(err)
		}
	}
	setup.Close()

	// Open a raw TCP client, authenticate via DialContext/TCP, start reading rows,
	// then stall before draining the full response and invoke owner db.Close().
	info := db.ConnectionInfo()
	raw, err := net.DialTimeout("tcp", info.Addr, 5*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer raw.Close()
	// Authenticate using standard sql client on a second connection? Better: use
	// openSQLClient and execute QueryContext, read 1st row (response is in flight),
	// leave Rows open while calling db.Close()!
	_ = raw.Close()
	reader := openSQLClient(t, ctx, db)
	defer reader.Close()
	rows, err := reader.conn.QueryContext(ctx, "SELECT id, body FROM big_close")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	// Close DB as owner while response / session is active.
	if err := db.Close(); err != nil {
		t.Fatalf("owner Close mid-response failed: %v\nlogs:\n%s", err, db.Logs())
	}
	if !strings.Contains(db.Logs(), "NATIVE_STOP mode=ordinary fast_shutdown=2 mode_applied=1 mode_err=0") {
		t.Fatalf("expected fast_shutdown=2 mode_applied=1 on mid-response Close, logs:\n%s", db.Logs())
	}
}

// P2-9 actual-guest regression: MARIAMEM_TIMING_DIR propagates guestTiming into
// native wire startup and records the full 8-event guest startup timing schema.
func TestNativeStartupGuestTimingRecorded(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("MARIAMEM_TIMING_DIR", dir)
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()

	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		db.Close()
		t.Fatal(err)
	}
	defer snap.Close()
	fork, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	_ = fork.Close()

	matches, err := filepath.Glob(filepath.Join(dir, "*-startup-*.json"))
	if err != nil || len(matches) < 2 {
		t.Fatalf("expected >=2 startup timing traces (fresh + fork), got %v err=%v", matches, err)
	}
	wantGuestEvents := []string{
		"guest_main", "restore_begin", "restore_complete", "open_begin",
		"server_init_begin", "server_init_complete", "bootstrap_complete", "ready_prepared",
	}
	for _, path := range matches {
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var trace struct {
			Operation string `json:"operation"`
			Events    []struct {
				Name string `json:"name"`
			} `json:"events"`
			Guest struct {
				Version int    `json:"version"`
				Clock   string `json:"clock"`
				Events  []struct {
					Name   string `json:"name"`
					Offset int64  `json:"offset_ns"`
				} `json:"events"`
			} `json:"guest"`
		}
		if err := json.Unmarshal(raw, &trace); err != nil {
			t.Fatalf("invalid trace JSON %s: %v", path, err)
		}
		if trace.Guest.Version != 1 || trace.Guest.Clock != "guest_monotonic" {
			t.Fatalf("missing/invalid guest timing in %s: %s", path, string(raw))
		}
		if len(trace.Guest.Events) != len(wantGuestEvents) {
			t.Fatalf("unexpected guest event count in %s: got %d want %d (%s)", path, len(trace.Guest.Events), len(wantGuestEvents), string(raw))
		}
		var prev int64
		for i, want := range wantGuestEvents {
			ev := trace.Guest.Events[i]
			if ev.Name != want || ev.Offset < prev || (i == 0 && ev.Offset != 0) {
				t.Fatalf("invalid guest event[%d] in %s: got %+v want %s prev=%d", i, path, ev, want, prev)
			}
			prev = ev.Offset
		}
		sawRead := false
		for _, ev := range trace.Events {
			if ev.Name == "guest_timing_read" {
				sawRead = true
			}
		}
		if !sawRead {
			t.Fatalf("missing host guest_timing_read marker in %s", path)
		}
	}
}
