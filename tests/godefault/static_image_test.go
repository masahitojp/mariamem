//go:build integration

package godefault

import (
	"testing"

	"github.com/masahitojp/mariamem"
)

func TestIndependentRootsAndSnapshotsRemainIsolated(t *testing.T) {
	ctx := t.Context()
	root, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = root.Close() })
	sql := pipePool(t, root)
	for _, query := range []string{"CREATE TABLE image_seed(id INT PRIMARY KEY,v INT)", "INSERT INTO image_seed VALUES(1,7)"} {
		if _, e = sql.ExecContext(ctx, query); e != nil {
			t.Fatal(e)
		}
	}
	if e = sql.Close(); e != nil {
		t.Fatal(e)
	}
	if e = root.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	snapshot, e := root.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = snapshot.Close() })
	for i := 0; i < 2; i++ {
		child, e := snapshot.Fork(ctx)
		if e != nil {
			t.Fatal(e)
		}
		conn := pipePool(t, child)
		var value int
		if e = conn.QueryRowContext(ctx, "SELECT v FROM image_seed WHERE id=1").Scan(&value); e != nil || value != 7 {
			t.Fatal(value, e)
		}
		if _, e = conn.ExecContext(ctx, "UPDATE image_seed SET v=99"); e != nil {
			t.Fatal(e)
		}
		if e = conn.Close(); e != nil {
			t.Fatal(e)
		}
		if e = child.WaitDisconnected(ctx); e != nil {
			t.Fatal(e)
		}
		if e = child.Close(); e != nil {
			t.Fatal(e)
		}
	}
	if e = snapshot.Close(); e != nil {
		t.Fatal(e)
	}
	independent, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = independent.Close() })
	conn := pipePool(t, independent)
	if _, e = conn.ExecContext(ctx, "SELECT * FROM image_seed"); e == nil {
		t.Fatal("application data leaked through initial image")
	}
	if e = conn.Close(); e != nil {
		t.Fatal(e)
	}
	if e = independent.Close(); e != nil {
		t.Fatal(e)
	}
}
