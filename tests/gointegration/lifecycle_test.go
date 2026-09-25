//go:build integration

package gointegration_test

import (
	"bytes"
	"context"
	"database/sql"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestPublicLifecycle(t *testing.T) {
	native := os.Getenv("MARIAMEM_NATIVE_DIR")
	if native == "" {
		t.Fatal("set MARIAMEM_NATIVE_DIR to an existing native bundle")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	own := func(db *mariamem.Database) *mariamem.Database {
		t.Helper()
		t.Cleanup(func() {
			if err := db.Close(); err != nil {
				t.Errorf("Database.Close: %v\n%s", err, db.Logs())
			}
		})
		return db
	}
	open := func(dsn string) *sql.DB {
		t.Helper()
		pool, err := sql.Open("mysql", dsn)
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() {
			if err := pool.Close(); err != nil {
				t.Error(err)
			}
		})
		if err := pool.PingContext(ctx); err != nil {
			t.Fatal(err)
		}
		return pool
	}
	disconnect := func(pool *sql.DB, db *mariamem.Database) {
		t.Helper()
		if err := pool.Close(); err != nil {
			t.Fatal(err)
		}
		if err := db.WaitDisconnected(ctx); err != nil {
			t.Fatal(err)
		}
	}
	count := func(pool *sql.DB, want int) {
		t.Helper()
		var got int
		if err := pool.QueryRowContext(ctx, "SELECT COUNT(*) FROM items").Scan(&got); err != nil {
			t.Fatal(err)
		}
		if got != want {
			t.Fatalf("row count=%d, want %d", got, want)
		}
	}
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: native})
	if err != nil {
		t.Fatal(err)
	}
	own(db)
	info := db.ConnectionInfo()
	config := mysql.NewConfig()
	config.Net = "tcp"
	config.Addr = net.JoinHostPort(info.Host, strconv.Itoa(info.Port))
	config.User, config.Passwd, config.DBName = info.User, info.Password, info.Database
	config.InterpolateParams = true // text-protocol compatibility, not Prepare support
	parsed, err := mysql.ParseDSN(db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	if !parsed.InterpolateParams || parsed.Addr != config.Addr || parsed.User != config.User || parsed.Passwd != config.Passwd || parsed.DBName != config.DBName {
		t.Fatalf("DSN and ConnectionInfo disagree: %+v", parsed)
	}
	infoPool := open(config.FormatDSN())
	var one int
	if err := infoPool.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil || one != 1 {
		t.Fatalf("SELECT 1: %d %v", one, err)
	}
	disconnect(infoPool, db)
	pool := open(db.DSN())
	var version string
	if err := pool.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(version, "MariaDB") {
		t.Fatalf("unexpected engine: %s", version)
	}
	t.Logf("driver=v1.9.3 server=%s", version)
	if _, err := pool.ExecContext(ctx, "CREATE TABLE items(id INT PRIMARY KEY, label VARCHAR(100)) ENGINE=InnoDB"); err != nil {
		t.Fatal(err)
	}
	var engine string
	if err := pool.QueryRowContext(ctx, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='items'").Scan(&engine); err != nil || engine != "InnoDB" {
		t.Fatalf("engine=%s error=%v", engine, err)
	}
	if _, err := pool.ExecContext(ctx, "INSERT INTO items VALUES (?, ?)", 1, "seed 'quoted'"); err != nil {
		t.Fatal(err)
	}
	var label string
	if err := pool.QueryRowContext(ctx, "SELECT label FROM items WHERE id=?", 1).Scan(&label); err != nil || label != "seed 'quoted'" {
		t.Fatalf("interpolated query: %q %v", label, err)
	}
	tx, err := pool.BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, "INSERT INTO items VALUES (?, ?)", 2, "committed"); err != nil {
		t.Fatal(err)
	}
	// Deliberate exception to disconnect-before-snapshot: verify active-tx rejection.
	// The wire reply can reach the client just before host session state becomes idle.
	rejectedPath := filepath.Join(t.TempDir(), "rejected")
	until := time.Now().Add(2 * time.Second)
	for {
		unexpected, snapshotErr := db.Snapshot(ctx, mariamem.SnapshotOptions{Destination: rejectedPath})
		if unexpected != nil {
			unexpected.Close()
			t.Fatal("active transaction snapshot succeeded")
		}
		if errors.Is(snapshotErr, mariamem.ErrBusy) && time.Now().Before(until) {
			time.Sleep(5 * time.Millisecond)
			continue
		}
		var detail *mariamem.HostError
		if !errors.Is(snapshotErr, mariamem.ErrTransactionActive) || !errors.As(snapshotErr, &detail) || detail.Closed || db.Closed() {
			t.Fatalf("transaction rejection: %v", snapshotErr)
		}
		break
	}
	if _, err := os.Lstat(rejectedPath); !os.IsNotExist(err) {
		t.Fatalf("rejection created destination: %v", err)
	}
	if err := tx.Commit(); err != nil {
		t.Fatal(err)
	}
	count(pool, 2)
	disconnect(pool, db)
	snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatalf("snapshot: %v\n%s", err, db.Logs())
	}
	t.Cleanup(func() {
		if err := snap.Close(); err != nil {
			t.Error(err)
		}
	})
	if !db.Closed() {
		t.Fatal("snapshot did not consume source")
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(snap.Path(), "manifest.json")); err != nil {
		t.Fatal(err)
	}
	type forkResult struct {
		db  *mariamem.Database
		err error
	}
	gate := make(chan struct{})
	results := make(chan forkResult, 2)
	for i := 0; i < 2; i++ {
		go func() {
			<-gate
			db, err := snap.Fork(ctx)
			results <- forkResult{db, err}
		}()
	}
	close(gate)
	var forks []*mariamem.Database
	var forkErr error
	for i := 0; i < 2; i++ {
		result := <-results
		if result.db != nil {
			forks = append(forks, own(result.db))
		}
		forkErr = errors.Join(forkErr, result.err)
	}
	if forkErr != nil {
		t.Fatal(forkErr)
	}
	a, b := forks[0], forks[1]
	ap, bp := open(a.DSN()), open(b.DSN())
	count(ap, 2)
	count(bp, 2)
	if _, err := ap.ExecContext(ctx, "INSERT INTO items VALUES (?, ?)", 3, "only A"); err != nil {
		t.Fatal(err)
	}
	count(ap, 3)
	count(bp, 2)
	// Removing the template must not affect already-started forks.
	if err := snap.Close(); err != nil {
		t.Fatal(err)
	}
	if err := snap.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Lstat(filepath.Dir(snap.Path())); !os.IsNotExist(err) {
		t.Fatalf("temporary snapshot remains: %v", err)
	}
	count(ap, 3)
	count(bp, 2)
	disconnect(ap, a)
	destination := filepath.Join(t.TempDir(), "explicit")
	saved, err := a.Snapshot(ctx, mariamem.SnapshotOptions{Destination: destination})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := saved.Close(); err != nil {
			t.Error(err)
		}
	})
	if !a.Closed() {
		t.Fatal("explicit snapshot did not consume source")
	}
	// Also retain sequential Fork coverage and verify the explicit saved image.
	c, err := saved.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	own(c)
	cp := open(c.DSN())
	count(cp, 3)
	disconnect(cp, c)
	if err := c.Close(); err != nil {
		t.Fatal(err)
	}
	marker := filepath.Join(destination, "manifest.json")
	before, err := os.ReadFile(marker)
	if err != nil {
		t.Fatal(err)
	}
	if err := saved.Close(); err != nil {
		t.Fatal(err)
	}
	if err := saved.Close(); err != nil {
		t.Fatal(err)
	}
	disconnect(bp, b)
	if _, err := b.Snapshot(ctx, mariamem.SnapshotOptions{Destination: destination}); err == nil || b.Closed() {
		t.Fatalf("existing destination rejection: %v", err)
	}
	after, err := os.ReadFile(marker)
	if err != nil || !bytes.Equal(before, after) {
		t.Fatalf("explicit snapshot changed: %v", err)
	}
	if _, err := os.Stat(filepath.Join(destination, "data")); err != nil {
		t.Fatal(err)
	}
	if err := b.Close(); err != nil {
		t.Fatal(err)
	}
	if err := b.Close(); err != nil {
		t.Fatal(err)
	}
	if !b.Closed() {
		t.Fatal("Close state not updated")
	}
	// Host listener must be gone after normal Close.
	conn, err := net.DialTimeout("tcp", net.JoinHostPort(b.ConnectionInfo().Host, strconv.Itoa(b.ConnectionInfo().Port)), time.Second)
	if err == nil {
		conn.Close()
		t.Fatal("listener remains after Close")
	}
	t.Log("Start, ConnectionInfo/DSN, SQL, InnoDB, commit, transaction rejection, disconnect, snapshot, concurrent/sequential fork isolation and cleanup passed")
}
