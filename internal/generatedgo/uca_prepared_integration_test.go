//go:build integration

package generatedgo

import (
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// The private switch is supplied at construction, never by guestEnvironment or
// the public API. Run this only against the newly generated prepared-table guest.
func TestPreparedUCATablesActualGuest(t *testing.T) {
	t.Setenv("MARIAMEM_UCA_VERIFY_INTERNAL", "1")
	for _, tc := range []struct {
		name                    string
		verify, timing, corrupt bool
	}{
		{"normal_ambient_ignored", false, false, false},
		{"profiling_does_not_verify", false, true, false},
		{"six_resolved_tables", true, false, false},
		{"corrupt_table_rejected", true, false, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var input, output, diagnostic bytes.Buffer
			sequence := uint32(0)
			frame := func(op byte, sql string) {
				sequence++
				packet := make([]byte, 13+len(sql))
				binary.LittleEndian.PutUint32(packet, uint32(9+len(sql)))
				packet[4] = op
				binary.LittleEndian.PutUint32(packet[5:], sequence)
				copy(packet[13:], sql)
				input.Write(packet)
			}
			frame(1, "")
			for _, encoding := range []string{"utf8mb3", "utf8mb4"} {
				frame(2, fmt.Sprintf("SELECT STRCMP(_%s'a' COLLATE %s_uca1400_ai_ci,_%s'A' COLLATE %s_uca1400_ai_ci)", encoding, encoding, encoding, encoding))
			}
			input.Write([]byte{0, 0, 0, 0})
			before := base.MemoryMappingStats()
			construct := func(h *host) (*base.Module, func() error, error) {
				if tc.verify {
					h.SetEnv(append(guestEnvironment(false, tc.timing), "MARIAMEM_UCA_VERIFY_INTERNAL=1"))
				}
				m, release, err := newMemoryModule(h)
				if err == nil && tc.corrupt {
					// Mutate one numeric cell after normal initialization, before execution.
					// Locate the exact source bytes, not a guessed data address.
					p := filepath.Join("..", "..", "benchmarks", "ucapreparedinput", "level0.u16le.json")
					raw, e := os.ReadFile(p)
					if e != nil {
						release()
						return nil, nil, e
					}
					var record struct {
						Data string `json:"data"`
					}
					if e = json.Unmarshal(raw, &record); e != nil {
						release()
						return nil, nil, e
					}
					blob, e := base64.StdEncoding.DecodeString(record.Data)
					if e != nil {
						release()
						return nil, nil, e
					}
					zip, e := gzip.NewReader(bytes.NewReader(blob))
					if e != nil {
						release()
						return nil, nil, e
					}
					table, e := io.ReadAll(io.LimitReader(zip, 918017))
					zip.Close()
					if e != nil || len(table) != 918016 {
						release()
						return nil, nil, fmt.Errorf("invalid test table: %v", e)
					}
					index := bytes.Index(m.Memory, table)
					if index < 0 || bytes.Index(m.Memory[index+1:], table) >= 0 {
						release()
						return nil, nil, fmt.Errorf("prepared table missing/ambiguous")
					}
					m.Memory[index] ^= 1
				}
				return m, release, err
			}
			done := startInstance(&input, &output, &diagnostic, "", nil, tc.timing, nil, construct)
			var err error
			select {
			case err = <-done:
			case <-time.After(30 * time.Second):
				t.Fatal("guest did not terminate")
			}
			if tc.corrupt {
				if err == nil || !strings.Contains(diagnostic.String(), "match=0") {
					t.Fatalf("corruption did not reach actual verifier: %v %s", err, diagnostic.String())
				}
			} else {
				if err != nil {
					t.Fatalf("guest: %v %s", err, diagnostic.String())
				}
				// Ready, one session and two successful SQL replies; no silent SQL failure.
				for i := 0; i < 4; i++ {
					var n uint32
					if err := binary.Read(&output, binary.LittleEndian, &n); err != nil {
						t.Fatal(err)
					}
					if n > 1<<20 || int(n) > output.Len() {
						t.Fatal("invalid frame length", n)
					}
					var reply struct {
						Result map[string]any `json:"result"`
					}
					if err := json.Unmarshal(output.Next(int(n)), &reply); err != nil {
						t.Fatal(err)
					}
					key := "ok"
					if i == 0 {
						key = "ready"
					}
					if reply.Result[key] != true {
						t.Fatalf("failed guest reply: %+v", reply)
					}
				}
				if output.Len() != 0 {
					t.Fatal("unexpected trailing reply")
				}
				logs := diagnostic.String()
				if tc.verify {
					for _, id := range []int{2048, 2304} {
						for level := 0; level < 3; level++ {
							marker := fmt.Sprintf("UCA_PREPARED_VERIFY id=%d level=%d bytes=918016 match=1", id, level)
							if !strings.Contains(logs, marker) {
								t.Fatalf("missing %s: %s", marker, logs)
							}
						}
					}
				} else if strings.Contains(logs, "UCA_PREPARED_VERIFY") {
					t.Fatal("ordinary execution performed verification", logs)
				}
			}
			after := base.MemoryMappingStats()
			if after["active_mappings"] != before["active_mappings"] {
				t.Fatal("mapping leak", before, after)
			}
		})
	}
}
