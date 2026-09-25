//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

type sqlClient struct {
	pool *sql.DB
	conn *sql.Conn
}

func openSQLClient(t *testing.T, ctx context.Context, db *mariamem.Database) *sqlClient {
	t.Helper()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	// Releasing a pinned sql.Conn must close its physical connection, so the
	// host can acknowledge guest session cleanup before reusing the slot.
	pool.SetMaxIdleConns(0)
	conn, err := pool.Conn(ctx)
	if err != nil {
		pool.Close()
		t.Fatal(err)
	}
	return &sqlClient{pool: pool, conn: conn}
}

func (c *sqlClient) Close() {
	if c.conn != nil {
		_ = c.conn.Close()
		c.conn = nil
	}
	if c.pool != nil {
		_ = c.pool.Close()
		c.pool = nil
	}
}

func queryInt(t *testing.T, ctx context.Context, c *sqlClient, statement string) int {
	t.Helper()
	var value int
	if err := c.conn.QueryRowContext(ctx, statement).Scan(&value); err != nil {
		t.Fatal(err)
	}
	return value
}

func TestMultipleClientIsolationAndCapacity(t *testing.T) {
	native := os.Getenv("MARIAMEM_NATIVE_DIR")
	if native == "" {
		t.Fatal("set MARIAMEM_NATIVE_DIR")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: native})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	b := openSQLClient(t, ctx, db)
	defer b.Close()
	if queryInt(t, ctx, a, "SELECT 1") != 1 || queryInt(t, ctx, b, "SELECT 2") != 2 {
		t.Fatal("ordinary queries failed")
	}
	if queryInt(t, ctx, a, "SELECT CONNECTION_ID()") == queryInt(t, ctx, b, "SELECT CONNECTION_ID()") {
		t.Fatal("two clients share a MariaDB session")
	}
	if _, err := a.conn.ExecContext(ctx, "SET @mariamem_test = 123"); err != nil {
		t.Fatal(err)
	}
	var other sql.NullInt64
	if err := b.conn.QueryRowContext(ctx, "SELECT @mariamem_test").Scan(&other); err != nil || other.Valid {
		t.Fatalf("session variable leaked: %+v %v", other, err)
	}
	if _, err := a.conn.ExecContext(ctx, "CREATE TEMPORARY TABLE local_only(id INT)"); err != nil {
		t.Fatal(err)
	}
	if err := b.conn.QueryRowContext(ctx, "SELECT COUNT(*) FROM local_only").Scan(new(int)); err == nil {
		t.Fatal("temporary table leaked to another session")
	}
	if _, err := a.conn.ExecContext(ctx, "CREATE TABLE shared_rows(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
		t.Fatal(err)
	}
	tx, err := a.conn.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := tx.ExecContext(ctx, "INSERT INTO shared_rows VALUES (1)"); err != nil {
		t.Fatal(err)
	}
	if got := queryInt(t, ctx, b, "SELECT COUNT(*) FROM shared_rows"); got != 0 {
		t.Fatalf("uncommitted row visible to B: %d", got)
	}
	if _, err := b.conn.ExecContext(ctx, "COMMIT"); err != nil {
		t.Fatal(err)
	}
	if got := queryInt(t, ctx, b, "SELECT COUNT(*) FROM shared_rows"); got != 0 {
		t.Fatalf("B committed A's transaction: %d", got)
	}
	if err := tx.Commit(); err != nil {
		t.Fatal(err)
	}
	if got := queryInt(t, ctx, b, "SELECT COUNT(*) FROM shared_rows"); got != 1 {
		t.Fatalf("A's commit not visible: %d", got)
	}
	tx, err = a.conn.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := tx.ExecContext(ctx, "INSERT INTO shared_rows VALUES (2)"); err != nil {
		t.Fatal(err)
	}
	if _, err := b.conn.ExecContext(ctx, "ROLLBACK"); err != nil {
		t.Fatal(err)
	}
	if got := queryInt(t, ctx, b, "SELECT COUNT(*) FROM shared_rows"); got != 1 {
		t.Fatalf("B rolled back A's transaction: %d", got)
	}
	if err := tx.Rollback(); err != nil {
		t.Fatal(err)
	}
	// Both sessions issue work at once. Correct results matter; no timing or
	// parallel speedup is assumed.
	start := make(chan struct{})
	results := make(chan error, 2)
	var wg sync.WaitGroup
	for _, c := range []*sqlClient{a, b} {
		wg.Add(1)
		go func(c *sqlClient) {
			defer wg.Done()
			<-start
			var slept int
			err := c.conn.QueryRowContext(ctx, "SELECT SLEEP(0.1)").Scan(&slept)
			if err == nil && slept != 0 {
				err = errors.New("SLEEP returned nonzero")
			}
			results <- err
		}(c)
	}
	close(start)
	wg.Wait()
	close(results)
	for err := range results {
		if err != nil {
			t.Fatal(err)
		}
	}
	// The current guest advertises 16 slots. Fill all of them, then verify
	// that the next connection receives a recoverable MySQL capacity error.
	clients := []*sqlClient{a, b}
	for len(clients) < 16 {
		clients = append(clients, openSQLClient(t, ctx, db))
	}
	defer func() {
		for _, c := range clients[2:] {
			c.Close()
		}
	}()
	extra, err := sql.Open("mysql", db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	var mysqlErr *mysql.MySQLError
	if err := extra.PingContext(ctx); !errors.As(err, &mysqlErr) || mysqlErr.Number != 1040 || !strings.Contains(mysqlErr.Message, "capacity") {
		t.Fatalf("capacity error: %v", err)
	}
	_ = extra.Close()
	if got := queryInt(t, ctx, b, "SELECT 1"); got != 1 || db.Err() != nil {
		t.Fatalf("capacity rejection damaged existing clients: %d %v", got, db.Err())
	}
	a.Close()
	var replacement *sqlClient
	for until := time.Now().Add(5 * time.Second); time.Now().Before(until); {
		candidate, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		candidate.SetMaxIdleConns(0)
		conn, err := candidate.Conn(ctx)
		if err == nil {
			replacement = &sqlClient{pool: candidate, conn: conn}
			break
		}
		_ = candidate.Close()
		if !errors.As(err, &mysqlErr) || mysqlErr.Number != 1040 {
			t.Fatalf("reconnect after release: %v", err)
		}
		time.Sleep(5 * time.Millisecond)
	}
	if replacement == nil {
		t.Fatal("released slot was not reusable")
	}
	defer replacement.Close()
	if err := replacement.conn.QueryRowContext(ctx, "SELECT @mariamem_test").Scan(&other); err != nil || other.Valid {
		t.Fatalf("slot reused with old variable: %+v %v", other, err)
	}
	if err := replacement.conn.QueryRowContext(ctx, "SELECT COUNT(*) FROM local_only").Scan(new(int)); err == nil {
		t.Fatal("slot reused with old temporary table")
	}
	if got := queryInt(t, ctx, b, "SELECT COUNT(*) FROM shared_rows"); got != 1 {
		t.Fatalf("surviving session damaged by reconnect: %d", got)
	}
	replacement.Close()
	for i := 0; i < 24; i++ {
		var recycled *sqlClient
		for until := time.Now().Add(5 * time.Second); time.Now().Before(until); {
			candidate, err := sql.Open("mysql", db.DSN())
			if err != nil {
				t.Fatal(err)
			}
			candidate.SetMaxIdleConns(0)
			conn, err := candidate.Conn(ctx)
			if err == nil {
				recycled = &sqlClient{pool: candidate, conn: conn}
				break
			}
			_ = candidate.Close()
			if !errors.As(err, &mysqlErr) || mysqlErr.Number != 1040 {
				t.Fatalf("cycle %d slot allocation: %v", i, err)
			}
			time.Sleep(5 * time.Millisecond)
		}
		if recycled == nil {
			t.Fatalf("cycle %d did not recover capacity", i)
		}
		if err := recycled.conn.QueryRowContext(ctx, "SELECT @mariamem_test").Scan(&other); err != nil || other.Valid {
			t.Fatalf("cycle %d inherited session state: %+v %v", i, other, err)
		}
		recycled.Close()
	}
	if db.Err() != nil {
		t.Fatalf("healthy DB invalidated: %v", db.Err())
	}
}

func TestMultipleClientSnapshotAndShutdown(t *testing.T) {
	native := os.Getenv("MARIAMEM_NATIVE_DIR")
	if native == "" {
		t.Fatal("set MARIAMEM_NATIVE_DIR")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: native})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	a := openSQLClient(t, ctx, db)
	defer a.Close()
	b := openSQLClient(t, ctx, db)
	defer b.Close()
	for _, c := range []*sqlClient{a, b} {
		tx, err := c.conn.BeginTx(ctx, nil)
		if err != nil {
			t.Fatal(err)
		}
		until := time.Now().Add(3 * time.Second)
		for {
			_, err = db.Snapshot(ctx, mariamem.SnapshotOptions{})
			if errors.Is(err, mariamem.ErrBusy) && time.Now().Before(until) {
				time.Sleep(5 * time.Millisecond)
				continue
			}
			break
		}
		if !errors.Is(err, mariamem.ErrTransactionActive) || db.Closed() {
			t.Fatalf("transaction in a session not detected: %v", err)
		}
		if err := tx.Rollback(); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := a.conn.ExecContext(ctx, "CREATE TABLE seeded(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
		t.Fatal(err)
	}
	if _, err := b.conn.ExecContext(ctx, "INSERT INTO seeded VALUES (1)"); err != nil {
		t.Fatal(err)
	}
	var snap *mariamem.Snapshot
	for until := time.Now().Add(3 * time.Second); time.Now().Before(until); {
		snap, err = db.Snapshot(ctx, mariamem.SnapshotOptions{})
		if !errors.Is(err, mariamem.ErrBusy) {
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	if !db.Closed() || db.Err() != nil {
		t.Fatalf("source not cleanly consumed: %v", db.Err())
	}
	if err := a.conn.PingContext(ctx); err == nil {
		t.Fatal("A remained connected after source snapshot")
	}
	if err := b.conn.PingContext(ctx); err == nil {
		t.Fatal("B remained connected after source snapshot")
	}
	fork, err := snap.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer fork.Close()
	c := openSQLClient(t, ctx, fork)
	defer c.Close()
	if got := queryInt(t, ctx, c, "SELECT COUNT(*) FROM seeded"); got != 1 {
		t.Fatalf("fork lost committed row: %d", got)
	}
	// Closing a separate DB with two idle clients must stop all sessions.
	before := childPIDs(t)
	other, err := mariamem.Start(ctx, mariamem.Options{NativeDir: native})
	if err != nil {
		t.Fatal(err)
	}
	var otherPID int
	for pid := range childPIDs(t) {
		if !before[pid] {
			otherPID = pid
		}
	}
	if otherPID == 0 {
		t.Fatal("guest process not found")
	}
	x := openSQLClient(t, ctx, other)
	y := openSQLClient(t, ctx, other)
	if err := other.Close(); err != nil {
		t.Fatal(err)
	}
	if err := syscall.Kill(otherPID, 0); !errors.Is(err, syscall.ESRCH) {
		t.Fatalf("guest process remains after Close: %v", err)
	}
	if err := other.Close(); err != nil {
		t.Fatal(err)
	}
	if err := x.conn.PingContext(ctx); err == nil {
		t.Fatal("first client remained connected after Close")
	}
	if err := y.conn.PingContext(ctx); err == nil {
		t.Fatal("second client remained connected after Close")
	}
	x.Close()
	y.Close()
}
