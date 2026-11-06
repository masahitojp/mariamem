//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

// Both transports share the session-map removal that wakes WaitDisconnected.
// The unit tests cover exact registration races; this covers real Serve cleanup,
// preservation after timeout, repeated registration, and subsequent capture/Fork.
func TestDisconnectNotificationTransports(t *testing.T) {
	for _, transport := range []string{"tcp", "pipe"} {
		t.Run(transport, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(t.Context(), time.Minute)
			defer cancel()
			db, err := mariamem.Start(ctx, mariamem.Options{})
			if err != nil {
				t.Fatal(err)
			}
			defer db.Close()
			for range 2 {
				var pool *sql.DB
				if transport == "pipe" {
					pool = pipePool(t, db)
				} else {
					pool, err = sql.Open("mysql", db.DSN())
					if err != nil {
						t.Fatal(err)
					}
					defer pool.Close()
				}
				if err = pool.PingContext(ctx); err != nil {
					t.Fatal(err)
				}
				bounded, stop := context.WithTimeout(ctx, 10*time.Millisecond)
				err = db.WaitDisconnected(bounded)
				stop()
				if !errors.Is(err, context.DeadlineExceeded) || db.Err() != nil {
					t.Fatalf("active session timeout invalidated DB: %v / %v", err, db.Err())
				}
				result := make(chan error, 4)
				for range 4 {
					go func() { result <- db.WaitDisconnected(ctx) }()
				}
				if err = pool.Close(); err != nil {
					t.Fatal(err)
				}
				for range 4 {
					select {
					case err = <-result:
						if err != nil {
							t.Fatal(err)
						}
					case <-ctx.Done():
						t.Fatal(ctx.Err())
					}
				}
			}
			snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
			if err != nil {
				t.Fatal(err)
			}
			defer snap.Close()
			for range 2 {
				child, err := snap.Fork(ctx)
				if err != nil {
					t.Fatal(err)
				}
				pool := pipePool(t, child)
				var n int
				if err = pool.QueryRowContext(ctx, "SELECT 42").Scan(&n); err != nil || n != 42 {
					t.Fatal(n, err)
				}
				if err = pool.Close(); err != nil {
					t.Fatal(err)
				}
				if err = child.WaitDisconnected(ctx); err != nil {
					t.Fatal(err)
				}
				if err = child.Close(); err != nil {
					t.Fatal(err)
				}
			}
		})
	}
}
