//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func keepExec(t *testing.T, ctx context.Context, c *sql.Conn, statements ...string) {
	t.Helper()
	for _, q := range statements {
		if _, err := c.ExecContext(ctx, q); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
	}
}

func keepRows(t *testing.T, ctx context.Context, c *sql.Conn) string {
	t.Helper()
	var got sql.NullString
	if err := c.QueryRowContext(ctx, "SELECT GROUP_CONCAT(CONCAT(id,'=',v) ORDER BY id) FROM keep_items").Scan(&got); err != nil {
		t.Fatal(err)
	}
	return got.String
}

type keepSession struct {
	id     int64
	marker string
	mode   string
}

func keepIdentity(t *testing.T, ctx context.Context, c *sql.Conn) keepSession {
	t.Helper()
	var s keepSession
	if err := c.QueryRowContext(ctx, "SELECT CONNECTION_ID(), @keep_marker, @@SESSION.sql_mode").Scan(&s.id, &s.marker, &s.mode); err != nil {
		t.Fatal(err)
	}
	return s
}

func keepChild(t *testing.T, ctx context.Context, snap *mariamem.Snapshot) (*mariamem.Database, *sqlClient) {
	t.Helper()
	child, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := child.Close(); err != nil {
			t.Error(err)
		}
	})
	c := openSQLClient(t, ctx, child)
	t.Cleanup(c.Close)
	return child, c
}

func noCrashRecovery(t *testing.T, db *mariamem.Database) {
	t.Helper()
	if strings.Contains(db.Logs(), "Starting crash recovery") {
		t.Fatal("child from a kept-database snapshot required crash recovery")
	}
}

// The source DB and its idle dedicated connections continue across the
// capture, and the baseline/source/children remain mutually isolated.
func TestSnapshotKeepDatabaseContinuesSourceAndConnections(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	b := openSQLClient(t, ctx, db)
	defer b.Close()
	keepExec(t, ctx, a.conn,
		"CREATE TABLE keep_items(id INT PRIMARY KEY, v INT) ENGINE=InnoDB",
		"INSERT INTO keep_items VALUES(1,10),(2,20)",
		"CREATE TABLE keep_plain(id INT PRIMARY KEY) ENGINE=MyISAM",
		"INSERT INTO keep_plain VALUES(7)",
		"SET @keep_marker='kept'",
		"SET SESSION sql_mode='ANSI_QUOTES'")
	before := keepIdentity(t, ctx, a.conn)
	var otherID int64
	if err := b.conn.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&otherID); err != nil {
		t.Fatal(err)
	}

	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 4})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	if got := snap.MaxForks(); got != 4 {
		t.Fatalf("KeepDatabase MaxForks = %d, want 4", got)
	}
	if db.Closed() || db.Err() != nil {
		t.Fatal("kept source was closed", db.Err())
	}
	if after := keepIdentity(t, ctx, a.conn); after != before {
		t.Fatalf("dedicated session changed across Snapshot: %+v -> %+v", before, after)
	}
	var otherAfter int64
	if err := b.conn.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&otherAfter); err != nil || otherAfter != otherID {
		t.Fatalf("second idle session changed: %d -> %d (%v)", otherID, otherAfter, err)
	}

	// Reads and writes continue on the same source and connection.
	keepExec(t, ctx, a.conn, "UPDATE keep_items SET v=99 WHERE id=1", "DELETE FROM keep_items WHERE id=2", "INSERT INTO keep_items VALUES(3,30)", "INSERT INTO keep_plain VALUES(8)")
	if got := keepRows(t, ctx, b.conn); got != "1=99,3=30" {
		t.Fatalf("source after capture %q", got)
	}

	first, fc := keepChild(t, ctx, snap)
	second, sc := keepChild(t, ctx, snap)
	noCrashRecovery(t, first)
	noCrashRecovery(t, second)
	for _, c := range []*sqlClient{fc, sc} {
		if got := keepRows(t, ctx, c.conn); got != "1=10,2=20" {
			t.Fatalf("child saw later source changes: %q", got)
		}
		if got := queryInt(t, ctx, c, "SELECT COUNT(*) FROM keep_plain"); got != 1 {
			t.Fatalf("child MyISAM rows %d", got)
		}
		var table, op, kind, text string
		if err := c.conn.QueryRowContext(ctx, "CHECK TABLE keep_plain").Scan(&table, &op, &kind, &text); err != nil || text != "OK" {
			t.Fatalf("child MyISAM check %q %q: %v", kind, text, err)
		}
	}
	keepExec(t, ctx, fc.conn, "UPDATE keep_items SET v=-1", "INSERT INTO keep_items VALUES(4,40)")
	if got := keepRows(t, ctx, sc.conn); got != "1=10,2=20" {
		t.Fatalf("sibling saw child changes: %q", got)
	}
	if got := keepRows(t, ctx, a.conn); got != "1=99,3=30" {
		t.Fatalf("source saw child changes: %q", got)
	}

	// The kept source can capture again; earlier baselines remain fixed.
	next, err := db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 2})
	if err != nil {
		t.Fatal(err)
	}
	defer next.Close()
	if after := keepIdentity(t, ctx, a.conn); after != before {
		t.Fatalf("dedicated session changed across second Snapshot: %+v", after)
	}
	_, nc := keepChild(t, ctx, next)
	if got := keepRows(t, ctx, nc.conn); got != "1=99,3=30" {
		t.Fatalf("second baseline %q", got)
	}
	_, tc := keepChild(t, ctx, snap)
	if got := keepRows(t, ctx, tc.conn); got != "1=10,2=20" {
		t.Fatalf("first baseline changed: %q", got)
	}

	// A Fork can keep itself too.
	derived, err := first.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	defer derived.Close()
	keepExec(t, ctx, fc.conn, "DELETE FROM keep_items")
	_, dc := keepChild(t, ctx, derived)
	if got := keepRows(t, ctx, dc.conn); got != "1=-1,2=-1,4=40" {
		t.Fatalf("derived baseline %q", got)
	}

	// The consuming Snapshot still applies to the same source afterwards.
	a.Close()
	b.Close()
	if err := db.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	last, err := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	defer last.Close()
	if !db.Closed() {
		t.Fatal("consuming Snapshot left source open")
	}
	_, lc := keepChild(t, ctx, last)
	if got := keepRows(t, ctx, lc.conn); got != "1=99,3=30" {
		t.Fatalf("consumed baseline %q", got)
	}
}

// An idle session holding LOCK TABLES WRITE may have unflushed non-transactional
// state (an observed MyISAM capture was corrupt), so KeepDatabase rejects it as
// busy. The rejection leaves the source, the holder's session and its locks.
func TestSnapshotKeepDatabaseRejectsLockTablesWrite(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	b := openSQLClient(t, ctx, db)
	defer b.Close()
	keepExec(t, ctx, a.conn,
		"CREATE TABLE keep_items(id INT PRIMARY KEY, v INT) ENGINE=InnoDB",
		"INSERT INTO keep_items VALUES(1,10)",
		"CREATE TABLE keep_plain(id INT PRIMARY KEY, v INT, KEY(v)) ENGINE=MyISAM",
		"INSERT INTO keep_plain VALUES(1,1)",
		"CREATE TABLE keep_aria(id INT PRIMARY KEY, v INT, KEY(v)) ENGINE=Aria TRANSACTIONAL=0",
		"INSERT INTO keep_aria VALUES(1,1)",
		"CREATE TABLE keep_unlocked(id INT) ENGINE=InnoDB",
		"SET @keep_marker='locked'")
	keepExec(t, ctx, b.conn, "SET @keep_marker='other'")
	holder, other := keepIdentity(t, ctx, a.conn), keepIdentity(t, ctx, b.conn)
	keepExec(t, ctx, a.conn, "LOCK TABLES keep_items WRITE, keep_plain WRITE",
		"INSERT INTO keep_items VALUES(2,20)", "INSERT INTO keep_plain VALUES(2,2),(3,3),(4,4)")

	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if snap != nil {
		if e := snap.Close(); e != nil {
			t.Error(e)
		}
	}
	var hostErr *mariamem.HostError
	if !errors.Is(err, mariamem.ErrBusy) || !errors.As(err, &hostErr) || hostErr.Closed {
		t.Fatalf("LOCK TABLES WRITE holder: want non-consuming ErrBusy, got %v", err)
	}
	if db.Closed() || db.Err() != nil {
		t.Fatal("rejection consumed the source", db.Err())
	}
	if got := keepIdentity(t, ctx, a.conn); got != holder {
		t.Fatalf("holder session changed: %+v -> %+v", holder, got)
	}
	if got := keepIdentity(t, ctx, b.conn); got != other {
		t.Fatalf("other session changed: %+v -> %+v", other, got)
	}
	// The holder is still in LOCK TABLES mode: an unlocked table is refused.
	var mysqlErr *mysql.MySQLError
	if _, err := a.conn.ExecContext(ctx, "SELECT COUNT(*) FROM keep_unlocked"); !errors.As(err, &mysqlErr) || mysqlErr.Number != 1100 {
		t.Fatalf("holder left LOCK TABLES mode: %v", err)
	}
	if got := keepRows(t, ctx, a.conn); got != "1=10,2=20" {
		t.Fatalf("holder rows %q", got)
	}
	// The rejected capture's global read lock is gone: another session writes
	// without waiting (a leftover lock would fail with 1205 after one second).
	keepExec(t, ctx, b.conn, "SET SESSION lock_wait_timeout=1", "INSERT INTO keep_unlocked VALUES(1)")

	keepExec(t, ctx, a.conn, "UNLOCK TABLES", "LOCK TABLES keep_aria WRITE",
		"INSERT INTO keep_aria VALUES(2,2),(3,3),(4,4)")
	ariaSnap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if ariaSnap != nil || !errors.Is(err, mariamem.ErrBusy) {
		t.Fatalf("Aria WRITE holder: snapshot=%v err=%v", ariaSnap, err)
	}
	keepExec(t, ctx, a.conn, "UNLOCK TABLES")
	snap, err = db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	if got := keepIdentity(t, ctx, a.conn); got != holder {
		t.Fatalf("holder session changed after retry: %+v", got)
	}
	// The accepted capture released its global read lock too.
	keepExec(t, ctx, b.conn, "INSERT INTO keep_unlocked VALUES(2)", "INSERT INTO keep_plain VALUES(5,5)",
		"INSERT INTO keep_aria VALUES(5,5)", "FLUSH TABLES WITH READ LOCK", "UNLOCK TABLES")
	_, c := keepChild(t, ctx, snap)
	if got := keepRows(t, ctx, c.conn); got != "1=10,2=20" {
		t.Fatalf("baseline InnoDB rows %q", got)
	}
	var table, op, kind, text string
	if err := c.conn.QueryRowContext(ctx, "CHECK TABLE keep_plain EXTENDED").Scan(&table, &op, &kind, &text); err != nil || text != "OK" {
		t.Fatalf("baseline MyISAM check %q %q: %v", kind, text, err)
	}
	if got := queryInt(t, ctx, c, "SELECT COUNT(*) FROM keep_plain"); got != 4 {
		t.Fatalf("baseline MyISAM rows %d", got)
	}
	if err := c.conn.QueryRowContext(ctx, "CHECK TABLE keep_aria EXTENDED").Scan(&table, &op, &kind, &text); err != nil || text != "OK" {
		t.Fatalf("baseline Aria check %q %q: %v", kind, text, err)
	}
	if got := queryInt(t, ctx, c, "SELECT COUNT(*) FROM keep_aria"); got != 4 {
		t.Fatalf("baseline Aria rows %d", got)
	}
}

// Rejections and waiting never consume the source or its connections.
func TestSnapshotKeepDatabasePreconditions(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	keepExec(t, ctx, a.conn, "CREATE TABLE keep_items(id INT PRIMARY KEY, v INT) ENGINE=InnoDB", "INSERT INTO keep_items VALUES(1,10)", "SET @keep_marker='kept'")
	before := keepIdentity(t, ctx, a.conn)
	keep := mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1}
	alive := func(stage string) {
		t.Helper()
		if db.Closed() {
			t.Fatalf("%s consumed the source", stage)
		}
		if after := keepIdentity(t, ctx, a.conn); after != before {
			t.Fatalf("%s changed the session: %+v", stage, after)
		}
	}

	var hostErr *mariamem.HostError
	if _, err := db.Snapshot(ctx, mariamem.SnapshotOptions{KeepDatabase: true, Rollback: true}); !errors.As(err, &hostErr) || hostErr.Code != "invalid_options" || hostErr.Closed {
		t.Fatalf("Rollback+KeepDatabase: %v", err)
	}
	alive("invalid options")

	keepExec(t, ctx, a.conn, "BEGIN", "UPDATE keep_items SET v=11")
	if _, err := db.Snapshot(ctx, keep); !errors.Is(err, mariamem.ErrTransactionActive) || !errors.As(err, &hostErr) || hostErr.Closed {
		t.Fatalf("open transaction: %v", err)
	}
	alive("open transaction")
	keepExec(t, ctx, a.conn, "COMMIT")

	// An in-flight command is waited for; a short ctx gives up without harm.
	b := openSQLClient(t, ctx, db)
	defer b.Close()
	slow := make(chan error, 1)
	go func() {
		_, err := b.conn.ExecContext(ctx, "DO SLEEP(1)")
		slow <- err
	}()
	time.Sleep(200 * time.Millisecond)
	short, stop := context.WithTimeout(ctx, 100*time.Millisecond)
	_, err = db.Snapshot(short, keep)
	stop()
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("bounded wait: %v", err)
	}
	alive("bounded wait")
	snap, err := db.Snapshot(ctx, keep)
	if err != nil {
		t.Fatal(err)
	}
	if err := <-slow; err != nil {
		t.Fatalf("in-flight command: %v", err)
	}
	alive("waited capture")
	_, c := keepChild(t, ctx, snap)
	if got := keepRows(t, ctx, c.conn); got != "1=11" {
		t.Fatalf("baseline %q", got)
	}
	if err := snap.Close(); err != nil {
		t.Fatal(err)
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Snapshot(ctx, keep); !errors.Is(err, mariamem.ErrClosed) {
		t.Fatalf("closed source: %v", err)
	}
}

// A prepared XA transaction is not committed state. It survives its client's
// disconnect, so KeepDatabase rejects it whether or not its session remains,
// without consuming the source or disturbing the other idle connections.
func TestSnapshotKeepDatabaseRejectsPreparedXA(t *testing.T) {
	for _, detached := range []bool{false, true} {
		name := "attached"
		if detached {
			name = "detached"
		}
		t.Run(name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
			defer cancel()
			db, err := mariamem.Start(ctx, mariamem.Options{})
			if err != nil {
				t.Fatal(err)
			}
			defer db.Close()
			a := openSQLClient(t, ctx, db)
			defer a.Close()
			x := openSQLClient(t, ctx, db)
			defer x.Close()
			keepExec(t, ctx, a.conn, "CREATE TABLE keep_items(id INT PRIMARY KEY, v INT) ENGINE=InnoDB",
				"INSERT INTO keep_items VALUES(1,10)", "SET @keep_marker='xa'")
			before := keepIdentity(t, ctx, a.conn)
			keepExec(t, ctx, x.conn, "XA START 'keep'", "INSERT INTO keep_items VALUES(2,20)", "XA END 'keep'", "XA PREPARE 'keep'")
			if detached {
				x.Close()
				// Wait until the server has retired the XA client's session.
				for {
					var n int
					if err := a.conn.QueryRowContext(ctx, "SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE COMMAND <> 'Daemon'").Scan(&n); err != nil {
						t.Fatal(err)
					}
					if n == 1 {
						break
					}
					time.Sleep(time.Millisecond)
				}
			}
			keep := mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1}
			snap, err := db.Snapshot(ctx, keep)
			if snap != nil {
				snap.Close()
			}
			var hostErr *mariamem.HostError
			if !errors.Is(err, mariamem.ErrTransactionActive) || !errors.As(err, &hostErr) || hostErr.Closed {
				t.Fatalf("prepared XA: want non-consuming ErrTransactionActive, got %v", err)
			}
			if db.Closed() || db.Err() != nil {
				t.Fatal("rejection consumed the source", db.Err())
			}
			if got := keepIdentity(t, ctx, a.conn); got != before {
				t.Fatalf("session changed: %+v -> %+v", before, got)
			}
			if got := keepRows(t, ctx, a.conn); got != "1=10" {
				t.Fatalf("prepared XA visible before commit: %q", got)
			}
			// The owner resolves an attached XA; any session resolves a detached one.
			resolver := x.conn
			if detached {
				resolver = a.conn
			}
			keepExec(t, ctx, resolver, "XA ROLLBACK 'keep'")
			snap, err = db.Snapshot(ctx, keep)
			if err != nil {
				t.Fatal(err)
			}
			defer snap.Close()
			if got := keepIdentity(t, ctx, a.conn); got != before {
				t.Fatalf("session changed after retry: %+v", got)
			}
			_, c := keepChild(t, ctx, snap)
			rows, err := c.conn.QueryContext(ctx, "XA RECOVER")
			if err != nil {
				t.Fatal(err)
			}
			if rows.Next() {
				t.Fatal("child inherited a prepared XA transaction")
			}
			rows.Close()
			if got := keepRows(t, ctx, c.conn); got != "1=10" {
				t.Fatalf("baseline %q", got)
			}
			c.Close()
			if err := snap.Close(); err != nil {
				t.Fatal(err)
			}

			// A consuming Snapshot after resolving a detached (or attached) XA
			// transaction must succeed and preserve committed state on Fork.
			consumedSnap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
			if err != nil {
				t.Fatalf("consuming Snapshot after resolved XA failed: %v", err)
			}
			defer consumedSnap.Close()
			_, c2 := keepChild(t, ctx, consumedSnap)
			rows2, err := c2.conn.QueryContext(ctx, "XA RECOVER")
			if err != nil {
				t.Fatal(err)
			}
			if rows2.Next() {
				t.Fatal("consuming snapshot child inherited a prepared XA transaction")
			}
			rows2.Close()
			if got := keepRows(t, ctx, c2.conn); got != "1=10" {
				t.Fatalf("consuming snapshot baseline %q", got)
			}
		})
	}
}

// The private capture session opens in the default database. When the user has
// dropped it, each attempt fails without leaking a session slot, so repeated
// failures never exhaust capacity and a repaired source captures normally.
func TestSnapshotKeepDatabaseOpenFailureReleasesSlot(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	keepExec(t, ctx, a.conn, "CREATE DATABASE keep_other", "CREATE TABLE keep_other.items(id INT PRIMARY KEY) ENGINE=InnoDB",
		"INSERT INTO keep_other.items VALUES(1)", "SET @keep_marker='open'", "DROP DATABASE test")
	before := keepIdentity(t, ctx, a.conn)
	keep := mariamem.SnapshotOptions{KeepDatabase: true, MaxForks: 1}
	for i := 0; i < 2*16+1; i++ { // more attempts than session capacity
		snap, err := db.Snapshot(ctx, keep)
		if snap != nil {
			snap.Close()
			t.Fatal("captured without a default database")
		}
		var hostErr *mariamem.HostError
		if !errors.As(err, &hostErr) || hostErr.Closed || hostErr.Code == "capacity" {
			t.Fatalf("attempt %d: %v", i, err)
		}
		if db.Closed() {
			t.Fatalf("attempt %d consumed the source", i)
		}
	}
	if got := keepIdentity(t, ctx, a.conn); got != before {
		t.Fatalf("session changed: %+v -> %+v", before, got)
	}
	keepExec(t, ctx, a.conn, "CREATE DATABASE test")
	snap, err := db.Snapshot(ctx, keep)
	if err != nil {
		t.Fatalf("after repair: %v", err)
	}
	defer snap.Close()
	if got := keepIdentity(t, ctx, a.conn); got != before {
		t.Fatalf("session changed after repair: %+v", got)
	}
	// After the successful capture, every slot but the held connection is available
	// (their DSN selects the repaired default database).
	extra := make([]*sqlClient, 0, 15)
	for i := 0; i < 15; i++ {
		c := openSQLClient(t, ctx, db)
		extra = append(extra, c)
		queryInt(t, ctx, c, "SELECT 1")
	}
	for _, c := range extra {
		c.Close()
	}
	_, c := keepChild(t, ctx, snap)
	if got := queryInt(t, ctx, c, "SELECT COUNT(*) FROM keep_other.items"); got != 1 {
		t.Fatalf("baseline rows %d", got)
	}
}
