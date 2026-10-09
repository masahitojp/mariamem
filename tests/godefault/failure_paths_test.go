//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// Representative cooperative failures, not a guarantee of forced guest kill.
// Deliberately retain closed handles and do not use GC/finalizers for cleanup.
func TestDefaultReleaseFailurePaths(t *testing.T) {
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	t.Setenv("MARIAMEM_RUNTIME", "")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	start := func() *mariamem.Database {
		t.Helper()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() {
			if err := db.Close(); err != nil {
				t.Error(err)
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
		t.Cleanup(func() { _ = pool.Close() })
		return pool
	}
	one := func(pool *sql.DB) {
		t.Helper()
		var got int
		if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&got); err != nil || got != 1 {
			t.Fatalf("healthy query: %d %v", got, err)
		}
	}
	countFD := func() int {
		t.Helper()
		dir, err := os.Open("/dev/fd")
		if err != nil {
			t.Fatal(err)
		}
		defer dir.Close()
		entries, err := dir.Readdirnames(-1)
		if err != nil {
			t.Fatal(err)
		}
		return len(entries)
	}
	warm := start()
	pool := open(warm.DSN())
	one(pool)
	if err := pool.Close(); err != nil {
		t.Fatal(err)
	}
	if err := warm.Close(); err != nil {
		t.Fatal(err)
	}
	fdsBefore, goroutinesBefore := countFD(), runtime.NumGoroutine()
	var retained []*mariamem.Database
	for round := 0; round < 2; round++ {
		db := start()
		retained = append(retained, db)
		config, err := mysql.ParseDSN(db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		config.Passwd = "deliberately-invalid-password"
		bad := open(config.FormatDSN())
		var auth *mysql.MySQLError
		if err := bad.PingContext(ctx); !errors.As(err, &auth) || auth.Number != 1045 {
			t.Fatalf("credential rejection: %v", err)
		}
		if err := bad.Close(); err != nil {
			t.Fatal(err)
		}
		good := open(db.DSN())
		for _, failure := range []struct {
			query  string
			number uint16
		}{
			{"NOT VALID SQL", 1064},
		} {
			_, err := good.ExecContext(ctx, failure.query)
			var sqlError *mysql.MySQLError
			if !errors.As(err, &sqlError) || sqlError.Number != failure.number {
				t.Fatalf("SQL rejection: %v", err)
			}
		}
		for _, query := range []string{"CREATE TABLE failure_check(id INT PRIMARY KEY)", "INSERT INTO failure_check VALUES(1)"} {
			if _, err := good.ExecContext(ctx, query); err != nil {
				t.Fatal(err)
			}
		}
		_, err = good.ExecContext(ctx, "INSERT INTO failure_check VALUES(1)")
		var constraint *mysql.MySQLError
		if !errors.As(err, &constraint) || constraint.Number != 1062 {
			t.Fatalf("constraint rejection: %v", err)
		}
		one(good)
		if db.Err() != nil || db.Closed() {
			t.Fatal("ordinary error invalidated DB", db.Err())
		}
		if err := good.Close(); err != nil {
			t.Fatal(err)
		}
		if err := db.WaitDisconnected(ctx); err != nil {
			t.Fatal(err)
		}
		reconnected := open(db.DSN())
		one(reconnected)
		// Leave an idle established session open while closing the server.
		if err := db.Close(); err != nil {
			t.Fatal(err)
		}
		if err := db.Close(); err != nil {
			t.Fatal(err)
		}
		if err := reconnected.PingContext(ctx); err == nil {
			t.Fatal("closed server answered SQL")
		}
		if err := reconnected.Close(); err != nil {
			t.Fatal(err)
		}
		unavailable := open(db.DSN())
		if err := unavailable.PingContext(ctx); err == nil {
			t.Fatal("connected to closed listener")
		}
		if err := unavailable.Close(); err != nil {
			t.Fatal(err)
		}
	}
	source := start()
	saved, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = saved.Close() })
	if err := source.Close(); err != nil {
		t.Fatal(err)
	}
	if err := saved.Close(); err != nil {
		t.Fatal(err)
	}
	canceled, stop := context.WithCancel(ctx)
	stop()
	for i := 0; i < 8; i++ {
		for _, opts := range []mariamem.Options{{StartupTimeout: -1}, {ShutdownTimeout: -1}, {QueryTimeout: -1}} {
			if db, err := mariamem.Start(ctx, opts); err == nil || db != nil {
				t.Fatalf("invalid options: %v %v", db, err)
			}
		}
		if db, err := mariamem.Start(canceled, mariamem.Options{}); !errors.Is(err, context.Canceled) || db != nil {
			t.Fatalf("canceled Start: %v %v", db, err)
		}
		if child, err := saved.Fork(ctx); err == nil || child != nil {
			t.Fatalf("closed snapshot: %v %v", child, err)
		}
	}
	t.Run("unusable_temporary_directory", func(t *testing.T) {
		file := filepath.Join(t.TempDir(), "not-a-directory")
		if err := os.WriteFile(file, nil, 0600); err != nil {
			t.Fatal(err)
		}
		t.Setenv("TMPDIR", file)
		for i := 0; i < 8; i++ {
			if db, err := mariamem.Start(ctx, mariamem.Options{}); err == nil || db != nil {
				t.Fatalf("unusable input: %v %v", db, err)
			}
		}
	})
	if err := saved.Close(); err != nil {
		t.Fatal(err)
	}
	if child, err := saved.Fork(ctx); !errors.Is(err, mariamem.ErrClosed) || child != nil {
		t.Fatalf("closed snapshot: %v %v", child, err)
	}
	recovered := start()
	finalPool := open(recovered.DSN())
	one(finalPool)
	if err := finalPool.Close(); err != nil {
		t.Fatal(err)
	}
	if err := recovered.Close(); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(2 * time.Second)
	for runtime.NumGoroutine() > goroutinesBefore+2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	fdsAfter, goroutinesAfter := countFD(), runtime.NumGoroutine()
	t.Logf("FDs=%d→%d goroutines=%d→%d", fdsBefore, fdsAfter, goroutinesBefore, goroutinesAfter)
	runtime.KeepAlive(warm)
	runtime.KeepAlive(retained)
	runtime.KeepAlive(source)
	runtime.KeepAlive(saved)
	runtime.KeepAlive(recovered)
	if fdsAfter != fdsBefore || goroutinesAfter > goroutinesBefore+2 {
		t.Fatal("resource growth after supported failure paths")
	}
}
