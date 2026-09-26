package guest

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/diagnostic"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestStartupDiagnostics(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := Start(ctx, filepath.Join(t.TempDir(), "missing"), "unused", "", "", "", nil)
	var detail *diagnostic.Error
	if !errors.As(err, &detail) || detail.Code != "guest_start" || detail.Stage != "guest_launch" || !errors.Is(err, os.ErrNotExist) || !strings.Contains(err.Error(), "executable permissions") {
		t.Fatalf("%v", err)
	}
	runtime := filepath.Join(t.TempDir(), "runtime")
	if err := os.WriteFile(runtime, []byte("#!/bin/sh\necho 'runtime cannot load guest' >&2\nexit 7\n"), 0700); err != nil {
		t.Fatal(err)
	}
	_, err = Start(ctx, runtime, "unused", "", "", "", nil)
	if !errors.As(err, &detail) || detail.Stage != "guest_ready" || !errors.Is(err, io.EOF) || !strings.Contains(err.Error(), "runtime cannot load guest") {
		t.Fatalf("%v", err)
	}
}
func TestStartupCauseAndBoundedTail(t *testing.T) {
	tail := &stderrTail{}
	tail.Write([]byte(strings.Repeat("x", 4096)))
	err := startupError(context.DeadlineExceeded, tail)
	if !errors.Is(err, context.DeadlineExceeded) || len(err.Error()) > 1600 {
		t.Fatalf("unbounded/lost cause: %v", err)
	}
}
