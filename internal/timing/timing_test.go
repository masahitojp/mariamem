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

func TestGuestFileDiagnosticsAreOptionalAndOutsideHostClock(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	ctx, _ := Begin(context.Background(), "startup")
	if !Enabled(ctx) || Enabled(context.Background()) {
		t.Fatal("opt-in state")
	}
	transfer := t.TempDir()
	ReadGuest(ctx, transfer) // absent older guest never fails startup
	trace := ctx.Value(key{}).(*Trace)
	if trace.Guest != nil {
		t.Fatal("fabricated guest events")
	}
	raw := []byte(`{"version":1,"clock":"guest_monotonic","events":[{"name":"guest_main","offset_ns":0}]}`)
	if err := os.WriteFile(filepath.Join(transfer, "startup-timing.json"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	ReadGuest(ctx, transfer)
	if string(trace.Guest) != string(raw) || len(trace.Events) != 1 {
		t.Fatal(trace)
	}
	if err := os.WriteFile(filepath.Join(transfer, "startup-timing.json"), []byte("invalid"), 0600); err != nil {
		t.Fatal(err)
	}
	ReadGuest(context.Background(), transfer) // disabled diagnostics do no I/O
}

func TestRecorderBindsConcurrentCallsWithoutPIDMatching(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	results := make(chan Trace, 2)
	for _, name := range []string{"one", "two"} {
		ctx := WithRecorder(context.Background(), func(trace Trace) { results <- trace })
		go func(name string, ctx context.Context) { ctx, finish := Begin(ctx, name); Mark(ctx, name); finish() }(name, ctx)
	}
	seen := map[string]bool{}
	for range 2 {
		trace := <-results
		seen[trace.Operation] = true
		if len(trace.Events) != 3 || trace.Events[1].Name != trace.Operation {
			t.Fatal(trace)
		}
	}
	if !seen["one"] || !seen["two"] {
		t.Fatal(seen)
	}
	t.Setenv("MARIAMEM_TIMING_DIR", "")
	_, finish := Begin(WithRecorder(context.Background(), func(Trace) { t.Fatal("disabled recorder called") }), "disabled")
	finish()
}
