package builtinruntime

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestCanceledPrepareCreatesNothing(t *testing.T) {
	dir := t.TempDir()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := Prepare(ctx, dir)
	if !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	files, err := os.ReadDir(dir)
	if err != nil || len(files) != 0 {
		t.Fatal(files, err)
	}
}

func TestPrepareNeverReplacesExistingImage(t *testing.T) {
	if _, _, err := image(); err != nil {
		t.Skip("unsupported build target")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "mariamem-guest")
	if err := os.WriteFile(path, []byte("owned file"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Prepare(context.Background(), dir); err == nil {
		t.Fatal("replaced existing file")
	}
	data, err := os.ReadFile(path)
	if err != nil || string(data) != "owned file" {
		t.Fatal(string(data), err)
	}
}
