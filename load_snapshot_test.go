package mariamem

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/runtimekind"
	stored "github.com/masahitojp/mariamem/internal/snapshot"
)

func persistedForLoad(t *testing.T, build string) string {
	t.Helper()
	transfer := t.TempDir()
	if err := os.Mkdir(filepath.Join(transfer, "data"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(transfer, "data", "seed"), []byte("prepared-state"), 0600); err != nil {
		t.Fatal(err)
	}
	dest := t.TempDir()
	if err := stored.Publish(transfer, dest, build); err != nil {
		t.Fatal(err)
	}
	return dest
}

func TestLoadSnapshotOwnsVerifiedBacking(t *testing.T) {
	ctx := context.Background()
	path := persistedForLoad(t, runtimekind.GuestSHA256)
	s, err := LoadSnapshot(ctx, path, Options{QueryTimeout: 3 * time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	if s.opts.QueryTimeout != 3*time.Second || s.opts.StartupTimeout == 0 {
		t.Fatal("Fork options were not normalized")
	}
	entries, release, err := s.backing.Acquire(runtimekind.GuestSHA256)
	if err != nil {
		t.Fatal(err)
	}
	fd := -1
	for _, entry := range entries {
		if !entry.Directory {
			fd = entry.FD
		}
	}
	if fd < 0 {
		t.Fatal("no owned backing")
	}
	if err := os.RemoveAll(path); err != nil {
		t.Fatal(err)
	}
	got := make([]byte, len("prepared-state"))
	_, err = syscall.Pread(fd, got, 0)
	release()
	if err != nil || string(got) != "prepared-state" {
		t.Fatalf("import depends on source: %q %v", got, err)
	}
	if err = s.Close(); err != nil {
		t.Fatal(err)
	}
	if err = s.Close(); err != nil {
		t.Fatal(err)
	}
	var st syscall.Stat_t
	if err = syscall.Fstat(fd, &st); err != syscall.EBADF {
		t.Fatalf("backing not released: %v", err)
	}
	if _, err = s.Fork(ctx); !errors.Is(err, ErrClosed) {
		t.Fatalf("closed Fork: %v", err)
	}
}

func TestLoadSnapshotPreservesPersistedArtifact(t *testing.T) {
	path := persistedForLoad(t, runtimekind.GuestSHA256)
	s, err := LoadSnapshot(context.Background(), path, Options{})
	if err != nil {
		t.Fatal(err)
	}
	if err = s.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err = os.Stat(filepath.Join(path, "manifest.json")); err != nil {
		t.Fatal(err)
	}
}

func TestLoadSnapshotRejectsInvalidInput(t *testing.T) {
	for _, kind := range []string{"corrupt", "missing", "manifest", "guest", "canceled", "options", "legacy"} {
		t.Run(kind, func(t *testing.T) {
			path := persistedForLoad(t, runtimekind.GuestSHA256)
			ctx := context.Background()
			opts := Options{}
			switch kind {
			case "corrupt":
				if err := os.WriteFile(filepath.Join(path, "data", "seed"), []byte("different-data"), 0600); err != nil {
					t.Fatal(err)
				}
			case "missing":
				if err := os.Remove(filepath.Join(path, "data", "seed")); err != nil {
					t.Fatal(err)
				}
			case "manifest":
				if err := os.WriteFile(filepath.Join(path, "manifest.json"), []byte("{"), 0600); err != nil {
					t.Fatal(err)
				}
			case "guest":
				b, err := os.ReadFile(filepath.Join(path, "manifest.json"))
				if err != nil {
					t.Fatal(err)
				}
				var m stored.Manifest
				if err = json.Unmarshal(b, &m); err != nil {
					t.Fatal(err)
				}
				m.WASM = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
				b, err = json.Marshal(m)
				if err != nil {
					t.Fatal(err)
				}
				if err = os.WriteFile(filepath.Join(path, "manifest.json"), b, 0600); err != nil {
					t.Fatal(err)
				}
			case "canceled":
				var cancel context.CancelFunc
				ctx, cancel = context.WithCancel(ctx)
				cancel()
			case "options":
				opts.QueryTimeout = -time.Second
			case "legacy":
				opts.NativeDir = "legacy"
			}
			s, err := LoadSnapshot(ctx, path, opts)
			if err == nil {
				s.Close()
				t.Fatal("invalid input accepted")
			}
			if s != nil {
				t.Fatal("failed import returned ownership")
			}
			if kind == "canceled" && !errors.Is(err, context.Canceled) {
				t.Fatalf("cancellation lost: %v", err)
			}
			if kind == "corrupt" || kind == "missing" || kind == "manifest" || kind == "guest" {
				var host *HostError
				if !errors.As(err, &host) || host.Code != "snapshot_failed" {
					t.Fatalf("import error contract: %v", err)
				}
			}
		})
	}
}
