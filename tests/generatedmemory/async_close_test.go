//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func TestPublicAsyncCloseForkLifecycle(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	before := base.MemoryMappingStats()
	root, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer root.Close()
	seed, e := sql.Open("mysql", root.DSN())
	if e != nil {
		t.Fatal(e)
	}
	if _, e = seed.ExecContext(ctx, "CREATE TABLE async_seed(v INT)"); e != nil {
		seed.Close()
		t.Fatal(e)
	}
	if _, e = seed.ExecContext(ctx, "INSERT INTO async_seed VALUES(1)"); e != nil {
		seed.Close()
		t.Fatal(e)
	}
	seed.Close()
	if e = root.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	snap, e := root.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
	if e != nil {
		t.Fatal(e)
	}
	defer snap.Close()
	var handles []*mariamem.CloseHandle
	for i := 0; i < 12; i++ {
		db, e := snap.Fork(ctx)
		if e != nil {
			t.Fatal(e)
		}
		pool, e := sql.Open("mysql", db.DSN())
		if e != nil {
			db.Close()
			t.Fatal(e)
		}
		var v int
		e = pool.QueryRowContext(ctx, "SELECT SUM(v) FROM async_seed").Scan(&v)
		pool.Close()
		if e != nil || v != 1 {
			db.Close()
			t.Fatal(v, e)
		}
		if e = db.WaitDisconnected(ctx); e != nil {
			db.Close()
			t.Fatal(e)
		}
		h, e := db.CloseAsync(ctx)
		if h != nil {
			handles = append(handles, h)
		}
		if e != nil {
			db.Close()
			t.Fatal(e)
		}
		if !db.Closed() {
			t.Fatal("not closed after stopping")
		}
		if _, e = db.Snapshot(ctx, mariamem.SnapshotOptions{}); !errors.Is(e, mariamem.ErrClosed) {
			t.Fatal(e)
		}
	}
	for _, h := range handles {
		if e = h.Wait(ctx); e != nil || !h.Disposed() {
			t.Fatal(e)
		}
	}
	if e = snap.Close(); e != nil {
		t.Fatal(e)
	}
	after := base.MemoryMappingStats()
	for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if before[key] != after[key] {
			t.Fatal("resource retained", key, before[key], after[key])
		}
	}
}
