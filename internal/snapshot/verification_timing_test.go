package snapshot

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/masahitojp/mariamem/internal/timing"
)

func TestPublishDiagnosticsPreservePublishedStateAndValidation(t *testing.T) {
	transfer := t.TempDir()
	if err := os.MkdirAll(filepath.Join(transfer, "data", "nested"), 0700); err != nil {
		t.Fatal(err)
	}
	for name, contents := range map[string]string{"one": "original", "nested/two": "second"} {
		if err := os.WriteFile(filepath.Join(transfer, "data", name), []byte(contents), 0600); err != nil {
			t.Fatal(err)
		}
	}
	untraced, traced := t.TempDir(), t.TempDir()
	t.Setenv("MARIAMEM_TIMING_DIR", "")
	if err := Publish(transfer, untraced, "build"); err != nil {
		t.Fatal(err)
	}
	t.Setenv("MARIAMEM_TIMING_DIR", t.TempDir())
	var trace timing.Trace
	ctx := timing.WithRecorder(context.Background(), func(tr timing.Trace) { trace = tr })
	if err := PublishContext(ctx, transfer, traced, "build"); err != nil {
		t.Fatal(err)
	}
	a, err := Validate(untraced, "build")
	if err != nil {
		t.Fatal(err)
	}
	b, err := Validate(traced, "build")
	if err != nil || !reflect.DeepEqual(a, b) {
		t.Fatalf("published state differs: %v", err)
	}
	var copied, hashed int64
	for _, event := range trace.Events {
		if event.Name == "copy_materialized" {
			copied += event.BytesRead
		} else if strings.HasSuffix(event.Name, "/read_hashed") {
			hashed += event.BytesRead
		}
	}
	if trace.Operation != "snapshot_publish" || copied != 14 || hashed != 28 {
		t.Fatalf("logical pass counts: copied=%d hashed=%d trace=%v", copied, hashed, trace)
	}
	if err := os.WriteFile(filepath.Join(traced, "data", "one"), []byte("changed!"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Validate(traced, "build"); err == nil {
		t.Fatal("traced publication accepted corruption")
	}
}

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
