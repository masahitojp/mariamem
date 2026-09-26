package timing

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

func TestOptInMonotonicTrace(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("MARIAMEM_TIMING_DIR", dir)
	ctx, finish := Begin(context.Background(), "startup")
	Mark(ctx, "spawn")
	finish()
	paths, _ := filepath.Glob(filepath.Join(dir, strconv.Itoa(os.Getpid())+"-startup-*.json"))
	if len(paths) != 1 {
		t.Fatal(paths)
	}
	raw, err := os.ReadFile(paths[0])
	if err != nil {
		t.Fatal(err)
	}
	var trace Trace
	if err = json.Unmarshal(raw, &trace); err != nil {
		t.Fatal(err)
	}
	if trace.Operation != "startup" || len(trace.Events) != 3 {
		t.Fatal(trace)
	}
	for i := 1; i < len(trace.Events); i++ {
		if trace.Events[i].Offset < trace.Events[i-1].Offset {
			t.Fatal(trace)
		}
	}
}
func TestDisabledAndUnavailableDestination(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", "")
	ctx, finish := Begin(context.Background(), "startup")
	Mark(ctx, "noop")
	finish()
	if ctx.Value(key{}) != nil {
		t.Fatal("disabled trace allocated")
	}
	t.Setenv("MARIAMEM_TIMING_DIR", filepath.Join(t.TempDir(), "missing"))
	ctx, finish = Begin(context.Background(), "startup")
	Mark(ctx, "ready")
	finish() // diagnostic I/O does not fail startup
}
