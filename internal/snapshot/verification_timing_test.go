package snapshot

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/masahitojp/mariamem/internal/timing"
)

func TestVerificationTimingPreservesIntegrityAndCountsReads(t *testing.T) {
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	transfer, destination := t.TempDir(), t.TempDir()
	if err := os.Mkdir(filepath.Join(transfer, "data"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(transfer, "data", "file"), []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Publish(transfer, destination, "build"); err != nil {
		t.Fatal(err)
	}
	var trace timing.Trace
	ctx := timing.WithRecorder(context.Background(), func(tr timing.Trace) { trace = tr })
	if _, err := ValidateTimed(ctx, destination, "build"); err != nil {
		t.Fatal(err)
	}
	manifest, _ := os.ReadFile(filepath.Join(destination, "manifest.json"))
	var bytes int64
	for _, e := range trace.Events {
		bytes += e.BytesRead
	}
	if trace.Operation != "snapshot_verification" || bytes != int64(len(manifest)+len("original")) {
		t.Fatal(trace)
	}
	raw, err := json.Marshal(trace)
	if err != nil || !json.Valid(raw) {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(destination, "data", "file"), []byte("modified"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateTimed(ctx, destination, "build"); err == nil {
		t.Fatal("instrumentation bypassed corrupt data")
	}
}
