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
			var diagnostic bytes.Buffer
			childIn, input, err := os.Pipe()
			if err != nil {
				t.Fatal(err)
			}
			output, childOut, err := os.Pipe()
			if err != nil {
				childIn.Close()
				input.Close()
				t.Fatal(err)
			}
			defer childIn.Close()
			defer input.Close()
			defer output.Close()
			defer childOut.Close()
			replies := make(chan error, 1)
			go func() {
				fail := func(err error) { input.Close(); replies <- err }
				read := func(ready bool) error {
					var n uint32
					if err := binary.Read(output, binary.LittleEndian, &n); err != nil {
						return err
					}
					if n > 1<<20 {
						return fmt.Errorf("invalid frame length %d", n)
					}
					raw := make([]byte, int(n))
					if _, err := io.ReadFull(output, raw); err != nil {
						return err
					}
					var reply struct {
						Result map[string]any `json:"result"`
					}
					if err := json.Unmarshal(raw, &reply); err != nil {
						return err
					}
					key := "ok"
					if ready {
						key = "ready"
					}
					if reply.Result[key] != true {
						return fmt.Errorf("failed guest reply: %+v", reply)
					}
					return nil
				}
				if err := read(true); err != nil {
					fail(err)
					return
				}
				sequence := uint32(0)
				call := func(op byte, sql string) error {
					sequence++
					packet := make([]byte, 13+len(sql))
					binary.LittleEndian.PutUint32(packet, uint32(9+len(sql)))
					packet[4] = op
					binary.LittleEndian.PutUint32(packet[5:], sequence)
					copy(packet[13:], sql)
					if _, err := input.Write(packet); err != nil {
						return err
					}
					return read(false)
				}
				if err := call(1, ""); err != nil {
					fail(err)
					return
				}
				for _, encoding := range []string{"utf8mb3", "utf8mb4"} {
					sql := fmt.Sprintf("SELECT STRCMP(_%s'a' COLLATE %s_uca1400_ai_ci,_%s'A' COLLATE %s_uca1400_ai_ci)", encoding, encoding, encoding, encoding)
					if err := call(2, sql); err != nil {
						fail(err)
						return
					}
				}
				_, err := input.Write([]byte{0, 0, 0, 0})
				replies <- err
			}()

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
					memory := m.Memory[:m.MemSize.Load()]
					index := bytes.Index(memory, table)
					if index < 0 || bytes.Index(memory[index+1:], table) >= 0 {
						release()
						return nil, nil, fmt.Errorf("prepared table missing/ambiguous")
					}
					m.Memory[index] ^= 1
				}
				return m, release, err
			}
			done := startInstance(childIn, childOut, &diagnostic, "", nil, tc.timing, nil, construct)
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
				select {
				case replyErr := <-replies:
					if replyErr != nil {
						t.Fatal(replyErr)
					}
				case <-time.After(time.Second):
					t.Fatal("missing successful replies")
				}

				logs := diagnostic.String()
				if tc.timing {
					t.Logf("ordinary profiling diagnostics: %s", logs)
				}
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
			input.Close()
			output.Close()
			childIn.Close()
			childOut.Close()
			if tc.corrupt {
				select {
				case <-replies:
				case <-time.After(time.Second):
					t.Fatal("transport goroutine retained")
				}
			}
			after := base.MemoryMappingStats()
			if after["active_mappings"] != before["active_mappings"] {
				t.Fatal("mapping leak", before, after)
			}
		})
	}
}
