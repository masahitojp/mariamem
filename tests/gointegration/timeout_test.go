//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// SELECT SLEEP runs inside the real guest without a table or a second session.
// Its duration is well beyond either test deadline, so completion cannot race
// with cancellation under normal scheduling.
func TestFatalQueryInterruption(t *testing.T) {
	native := os.Getenv("MARIAMEM_NATIVE_DIR")
	if native == "" {
		t.Fatal("set MARIAMEM_NATIVE_DIR to an existing native bundle")
	}
	for _, tc := range []struct {
		name        string
		queryLimit  time.Duration
		clientCause error
	}{
		{"host_timeout", time.Second, nil},
		{"client_deadline", 10 * time.Second, context.DeadlineExceeded},
		{"client_cancel", 10 * time.Second, context.Canceled},
	} {
		t.Run(tc.name, func(t *testing.T) {
			before := childPIDs(t)
			db, err := mariamem.Start(context.Background(), mariamem.Options{NativeDir: native, QueryTimeout: tc.queryLimit})
			if err != nil {
				t.Fatal(err)
			}
			t.Cleanup(func() { _ = db.Close() })
			var guestPID int
			for pid := range childPIDs(t) {
				if !before[pid] {
					guestPID = pid
				}
			}
			if guestPID == 0 {
				t.Fatal("guest child process not found")
			}
			pool, err := sql.Open("mysql", db.DSN())
			if err != nil {
				t.Fatal(err)
			}
			pool.SetMaxOpenConns(1)
			if err := pool.Ping(); err != nil {
				t.Fatal(err)
			}
			var value int
			if err := pool.QueryRow("SELECT * FROM mariamem_missing_table").Scan(&value); err == nil || db.Err() != nil {
				t.Fatalf("ordinary SQL error invalidated DB: query=%v instance=%v", err, db.Err())
			}
			ctx := context.Background()
			if tc.clientCause == context.DeadlineExceeded {
				var cancel context.CancelFunc
				ctx, cancel = context.WithTimeout(ctx, 200*time.Millisecond)
				defer cancel()
			} else if tc.clientCause == context.Canceled {
				var cancel context.CancelFunc
				ctx, cancel = context.WithCancel(ctx)
				defer cancel()
				go func() {
					time.Sleep(200 * time.Millisecond)
					cancel()
				}()
			}
			queryErr := pool.QueryRowContext(ctx, "SELECT SLEEP(10)").Scan(&value)
			if queryErr == nil {
				t.Fatal("long query unexpectedly completed")
			}
			if tc.clientCause != nil && !errors.Is(queryErr, tc.clientCause) {
				t.Fatalf("client cancellation cause lost: %v", queryErr)
			}
			if tc.clientCause == nil && !strings.Contains(queryErr.Error(), "database instance terminated") {
				t.Fatalf("host timeout returned an opaque error: %v", queryErr)
			}
			deadline := time.Now().Add(5 * time.Second)
			for db.Err() == nil && time.Now().Before(deadline) {
				time.Sleep(10 * time.Millisecond)
			}
			if !db.Closed() || !errors.Is(db.Err(), mariamem.ErrUnusable) {
				t.Fatalf("database remained usable: %v", db.Err())
			}
			if tc.clientCause == nil && !errors.Is(db.Err(), context.DeadlineExceeded) {
				t.Fatalf("host deadline cause lost: %v", db.Err())
			}
			if _, err := db.Snapshot(context.Background(), mariamem.SnapshotOptions{}); !errors.Is(err, mariamem.ErrUnusable) {
				t.Fatalf("snapshot after fatal query: %v", err)
			}
			if err := pool.QueryRow("SELECT 1").Scan(&value); err == nil {
				t.Fatal("query succeeded after invalidation")
			}
			if err := pool.Close(); err != nil {
				t.Fatal(err)
			}
			if err := db.Close(); err != nil {
				t.Fatalf("close after invalidation: %v", err)
			}
			if err := db.Close(); err != nil {
				t.Fatalf("repeated close: %v", err)
			}
			if err := syscall.Kill(guestPID, 0); !errors.Is(err, syscall.ESRCH) {
				t.Fatalf("guest PID %d still exists: %v", guestPID, err)
			}
		})
	}
}

func childPIDs(t *testing.T) map[int]bool {
	t.Helper()
	b, err := exec.Command("pgrep", "-P", strconv.Itoa(os.Getpid())).Output()
	if err != nil {
		var exit *exec.ExitError
		if errors.As(err, &exit) && exit.ExitCode() == 1 {
			return map[int]bool{}
		}
		t.Fatal(err)
	}
	result := make(map[int]bool)
	for _, line := range strings.Fields(string(b)) {
		pid, err := strconv.Atoi(line)
		if err != nil {
			t.Fatal(err)
		}
		result[pid] = true
	}
	return result
}
