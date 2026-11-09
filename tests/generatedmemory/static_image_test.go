//go:build integration

package godefault

import (
	"testing"

	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/image"
)

// Internal ownership diagnostics stay in the repository-only suite. The
// external godefault consumer separately checks SQL and Snapshot isolation.
func TestProcessImageSurvivesIndependentRootsAndSnapshots(t *testing.T) {
	ctx := t.Context()
	before := image.Stats()["acquires"].(int)
	root, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = root.Close() })
	snapshot, err := root.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = snapshot.Close() })
	for i := 0; i < 2; i++ {
		child, err := snapshot.Fork(ctx)
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = child.Close() })
		if err = child.Close(); err != nil {
			t.Fatal(err)
		}
	}
	if err = snapshot.Close(); err != nil {
		t.Fatal(err)
	}
	independent, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = independent.Close() })
	if err = independent.Close(); err != nil {
		t.Fatal(err)
	}
	stats := image.Stats()
	if stats["builds"].(int) != 1 || stats["acquires"].(int) != before+4 || stats["owned_fds"].(int) != 1 || stats["failed"].(bool) || stats["cleanup_debt"].(bool) {
		t.Fatal(stats)
	}
	if base.MemoryMappingStats()["active_mappings"] != 0 {
		t.Fatal("per-DB mapping retained", base.MemoryMappingStats())
	}
	t.Logf("retained process image: %v", stats)
}
