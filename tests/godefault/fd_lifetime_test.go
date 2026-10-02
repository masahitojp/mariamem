//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"os"
	"runtime"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

// Retaining a closed public Database must not retain its control pipe FD.
// No GC/finalizer is used: descriptor release belongs to normal Close.
func TestClosedDatabaseRetainedPipeLifetime(t *testing.T) {
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	t.Setenv("MARIAMEM_RUNTIME", "")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	// Initialize Go networking poller before recording the stable process boundary.
	warm, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	if err := warm.Close(); err != nil {
		t.Fatal(err)
	}
	count := func() int {
		directory, err := os.Open("/dev/fd")
		if err != nil {
			t.Skipf("descriptor inventory unavailable: %v", err)
		}
		defer directory.Close()
		entries, err := directory.Readdirnames(-1)
		if err != nil {
			t.Skipf("descriptor inventory unavailable: %v", err)
		}
		return len(entries)
	}
	before := count()
	var held []*mariamem.Database
	for round := 0; round < 3; round++ {
		// Two simultaneously live DBs; close one while the other still answers SQL.
		a, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = a.Close() })
		b, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = b.Close() })
		held = append(held, a, b)
		if err := a.Close(); err != nil {
			t.Fatal(err)
		}
		conn, err := sql.Open("mysql", b.DSN())
		if err != nil {
			t.Fatal(err)
		}
		var one int
		err = conn.QueryRowContext(ctx, "SELECT 1").Scan(&one)
		conn.Close()
		if err != nil || one != 1 {
			t.Fatalf("independent live DB: %d %v", one, err)
		}
		if err := b.Close(); err != nil {
			t.Fatal(err)
		}
		if err := a.Close(); err != nil {
			t.Fatal(err)
		}
		if err := b.Close(); err != nil {
			t.Fatal(err)
		}
	}
	// Snapshot consumes the source through Export rather than Shutdown. Its
	// response reader must have the same lifetime even while the handle stays live.
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = source.Close() })
	snapshot, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = snapshot.Close() })
	if err := source.Close(); err != nil {
		t.Fatal(err)
	}
	if err := snapshot.Close(); err != nil {
		t.Fatal(err)
	}
	after := count()
	t.Logf("retained closed handles=%d descriptors before=%d after=%d", len(held), before, after)
	runtime.KeepAlive(warm)
	runtime.KeepAlive(held)
	runtime.KeepAlive(source)
	runtime.KeepAlive(snapshot)
	if after != before {
		t.Fatalf("Close retained descriptors: before=%d after=%d", before, after)
	}
}
