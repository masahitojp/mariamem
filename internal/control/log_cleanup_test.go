package control

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestOwnedLogCleanupClosesBeforeRemoval(t *testing.T) {
	for _, route := range []string{"startup", "database"} {
		for _, owned := range []bool{false, true} {
			t.Run(fmt.Sprintf("%s/owned=%t", route, owned), func(t *testing.T) {
				name := filepath.Join(t.TempDir(), "owned.log")
				f, err := os.OpenFile(name, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
				if err != nil {
					t.Fatal(err)
				}
				t.Cleanup(func() { _ = f.Close() })
				cleanup := func() error { return cleanupOwnedLog(f, name, owned) }
				if route == "database" {
					d := &db{log: f, logPath: name, ownedLog: owned}
					cleanup = d.cleanupLog
				}
				if err := cleanup(); err != nil {
					t.Fatal(err)
				}
				if _, err := f.Write([]byte("unexpected")); !errors.Is(err, os.ErrClosed) {
					t.Fatal("writer remains open", err)
				}
				_, err = os.Stat(name)
				if owned && !errors.Is(err, os.ErrNotExist) {
					t.Fatal("owned log remains", err)
				}
				if !owned && err != nil {
					t.Fatal("caller log removed", err)
				}
				if err := cleanup(); err != nil {
					t.Fatal("retry", err)
				}
			})
		}
	}
}

func TestDatabaseLogCleanupRetriesRemovalAfterClosingWriter(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "writer-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = f.Close() })
	// A nonempty directory deterministically refuses removal on every OS.
	path := t.TempDir()
	blocker := filepath.Join(path, "blocker")
	if err := os.WriteFile(blocker, nil, 0600); err != nil {
		t.Fatal(err)
	}
	d := &db{log: f, logPath: path, ownedLog: true}
	if err := d.cleanupLog(); err == nil {
		t.Fatal("lost removal failure")
	}
	if _, err := f.Write(nil); !errors.Is(err, os.ErrClosed) {
		t.Fatal("removal failure left writer open", err)
	}
	if err := os.Remove(blocker); err != nil {
		t.Fatal(err)
	}
	if err := d.cleanupLog(); err != nil {
		t.Fatal("retry", err)
	}
	if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("retry left owned path", err)
	}
}
