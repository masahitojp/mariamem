package host

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

// In-memory framed fixtures exercise export/publication failure without a
// second runtime or production function/address-specific hooks.
func snapshotGuest(ctx context.Context, mode, destination string) (*guest.Process, error) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	go func() {
		defer childIn.Close()
		defer childOut.Close()
		send := func(result map[string]any) {
			b, _ := json.Marshal(map[string]any{"request_id": 0, "result": result})
			_ = binary.Write(childOut, binary.LittleEndian, uint32(len(b)))
			_, _ = childOut.Write(b)
		}
		send(map[string]any{"ready": true, "api_version": 2, "max_sessions": 16, "snapshot_version": 1})
		var op uint32
		err := binary.Read(childIn, binary.LittleEndian, &op)
		if err == nil && op == 0xfffffffe {
			if mode == "publish-failure" {
				err = os.Mkdir(filepath.Join(destination, "manifest.pending"), 0700)
			}
			send(map[string]any{"snapshot": mode != "export-failure", "snapshot_version": 1})
		}
		childIn.Close()
		childOut.Close()
		if errors.Is(err, io.EOF) {
			err = nil
		}
		completed <- err
	}()
	return guest.Connect(ctx, in, out, completed, nil, io.Discard)
}

type unusedListener struct{}

func (unusedListener) Accept() (net.Conn, error) { return nil, errors.New("unused") }
func (unusedListener) Close() error              { return nil }
func (unusedListener) Addr() net.Addr            { return nil }

func TestSnapshotDestination(t *testing.T) {
	for _, mode := range []string{"success", "publish-failure", "export-failure", "existing"} {
		t.Run(mode, func(t *testing.T) {
			root := t.TempDir()
			transfer := filepath.Join(root, "transfer")
			destination := filepath.Join(root, "saved")
			if err := os.MkdirAll(filepath.Join(transfer, "data"), 0700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(transfer, "data", "table"), []byte("seed"), 0600); err != nil {
				t.Fatal(err)
			}
			if mode == "existing" {
				if err := os.Mkdir(destination, 0700); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(destination, "keep"), []byte("original"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			p, err := snapshotGuest(ctx, mode, destination)
			if err != nil {
				t.Fatal(err)
			}
			defer p.AbortAndWait(errors.New("test cleanup"))
			s := &Server{Guest: p, listener: unusedListener{}, transfer: transfer, build: "test-build"}
			closed, err := s.Snapshot(ctx, destination, false)
			switch mode {
			case "success":
				if err != nil || !closed {
					t.Fatalf("closed=%v error=%v", closed, err)
				}
				if _, err := snapshot.Validate(destination, s.build); err != nil {
					t.Fatal(err)
				}
				if _, err := os.Stat(filepath.Join(destination, "manifest.pending")); !os.IsNotExist(err) {
					t.Fatalf("pending: %v", err)
				}
				// A pending manifest alone still cannot commit a snapshot.
				marker := filepath.Join(destination, "manifest.json")
				pending := filepath.Join(destination, "manifest.pending")
				if err := os.Rename(marker, pending); err != nil {
					t.Fatal(err)
				}
				if _, err := snapshot.Validate(destination, s.build); err == nil {
					t.Fatal("accepted uncommitted snapshot")
				}
				if err := os.Rename(pending, marker); err != nil {
					t.Fatal(err)
				}
				if _, err := snapshot.Validate(destination, s.build); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(destination, "data", "table"), []byte("changed"), 0600); err != nil {
					t.Fatal(err)
				}
				if _, err := snapshot.Validate(destination, s.build); err == nil {
					t.Fatal("accepted modified data")
				}
			case "existing":
				var rejected *Rejected
				if closed || !errors.As(err, &rejected) || rejected.Code != "destination" {
					t.Fatalf("closed=%v error=%v", closed, err)
				}
				b, err := os.ReadFile(filepath.Join(destination, "keep"))
				if err != nil || string(b) != "original" {
					t.Fatalf("existing data changed: %q %v", b, err)
				}
			default:
				if err == nil || !closed {
					t.Fatalf("closed=%v error=%v", closed, err)
				}
				if mode == "publish-failure" && !strings.Contains(err.Error(), "manifest.pending") {
					t.Fatalf("lost publication error: %v", err)
				}
				if mode == "export-failure" && !strings.Contains(err.Error(), "invalid snapshot acknowledgement") {
					t.Fatalf("lost export error: %v", err)
				}
				if _, err := os.Lstat(destination); !os.IsNotExist(err) {
					t.Fatalf("partial destination remains: %v", err)
				}
			}
		})
	}
}
