package host

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
)

// Inspect the mode at the actual stop frame; a rejected setting must never
// reach shutdown/export or publish a recoverable root as a clean snapshot.
func TestShutdownPurposeAndSettingFailure(t *testing.T) {
	for _, purpose := range []shutdownPurpose{shutdownDiscard, shutdownCapture, shutdownExport} {
		for _, reject := range []bool{false, true} {
			t.Run(string(rune('0'+purpose))+map[bool]string{false: "success", true: "rejected"}[reject], func(t *testing.T) {
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
				defer cancel()
				childIn, in := io.Pipe()
				out, childOut := io.Pipe()
				completed := make(chan error, 1)
				observed := make(chan string, 1)
				go func() {
					defer childIn.Close()
					defer childOut.Close()
					send := func(id uint32, result map[string]any) {
						b, _ := json.Marshal(map[string]any{"request_id": id, "result": result})
						_ = binary.Write(childOut, binary.LittleEndian, uint32(len(b)))
						_, _ = childOut.Write(b)
					}
					send(0, map[string]any{"ready": true, "api_version": 2, "max_sessions": 16, "snapshot_version": 1})
					mode := "unset"
					for {
						var n uint32
						if e := binary.Read(childIn, binary.LittleEndian, &n); e != nil {
							observed <- "aborted"
							completed <- nil
							return
						}
						if n == 0 || n == 0xfffffffe {
							observed <- mode
							if n == 0xfffffffe {
								send(0, map[string]any{"snapshot": true, "snapshot_version": 1})
							}
							completed <- nil
							return
						}
						b := make([]byte, n)
						if _, e := io.ReadFull(childIn, b); e != nil {
							completed <- e
							return
						}
						result := map[string]any{"ok": true}
						if b[0] == 2 {
							mode = string(b[9:])
							if reject {
								result = map[string]any{"ok": false, "errno": 1231, "error": "setting rejected"}
							}
						}
						send(binary.LittleEndian.Uint32(b[1:]), result)
					}
				}()
				p, e := guest.Connect(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard)
				if e != nil {
					t.Fatal(e)
				}
				defer p.AbortAndWait(errors.New("cleanup"))
				s := &Server{Guest: p}
				e = s.finish(ctx, purpose)
				got := <-observed
				if reject {
					if e == nil || !strings.Contains(e.Error(), "setting rejected") || got != "aborted" {
						t.Fatalf("error=%v observed=%q", e, got)
					}
				} else {
					want := "SET GLOBAL innodb_fast_shutdown=1"
					if purpose == shutdownDiscard {
						want = "SET GLOBAL innodb_fast_shutdown=2"
					}
					if e != nil || got != want {
						t.Fatalf("error=%v observed=%q want=%q", e, got, want)
					}
				}
			})
		}
	}
}
