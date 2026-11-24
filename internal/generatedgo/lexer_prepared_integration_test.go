//go:build integration

package generatedgo

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// The private switch is supplied at construction, never by guestEnvironment or
// the public API. Run this only against the newly generated prepared-table guest.
func TestPreparedLexerTablesActualGuest(t *testing.T) {
	t.Setenv("MARIAMEM_LEXER_VERIFY_INTERNAL", "1")
	for _, tc := range []struct {
		name                    string
		verify, timing, corrupt bool
	}{
		{"normal_ambient_ignored", false, false, false},
		{"profiling_does_not_verify", false, true, false},
		{"all_638_compiled_descriptors", true, false, false},
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
				queries := make([]string, 0, 2)
				for _, encoding := range []string{"utf8mb3", "utf8mb4"} {
					queries = append(queries, fmt.Sprintf("SELECT STRCMP(_%s'a' COLLATE %s_uca1400_ai_ci,_%s'A' COLLATE %s_uca1400_ai_ci)", encoding, encoding, encoding, encoding))
				}
				err := runWireSQLQueries(input, output, queries)
				if err != nil {
					input.Close()
				}
				replies <- err
			}()

			before := base.MemoryMappingStats()
			construct := func(h *host) (*base.Module, func() error, error) {
				if tc.verify {
					h.SetEnv(append(wireGuestEnvironment(false, tc.timing), "MARIAMEM_CONTROL_EPOCH=1", "MARIAMEM_LEXER_VERIFY_INTERNAL=1"))
				}
				m, release, err := newMemoryModule(h)
				if err == nil && tc.corrupt {
					// Mutate one numeric cell after normal initialization, before execution.
					// Locate the exact source bytes, not a guessed data address.
					p := filepath.Join("..", "..", "benchmarks", "lexerpreparedinput", "input.json")
					raw, e := os.ReadFile(p)
					if e != nil {
						release()
						return nil, nil, e
					}
					var record struct {
						Data string `json:"data_hex"`
					}
					if e = json.Unmarshal(raw, &record); e != nil {
						release()
						return nil, nil, e
					}
					table, e := hex.DecodeString(record.Data)
					if e != nil || len(table) != 14336 {
						release()
						return nil, nil, fmt.Errorf("invalid lexer table: %v", e)
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
			done := startWireInstance(childIn, childOut, &diagnostic, "", nil, tc.timing, nil, construct, 1, &WireLifecycle{Capture: &prepared.Capture{}, Approval: make(chan error, 1)})
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
					if strings.Count(logs, "LEXER_PREPARED_VERIFY id=") != 638 {
						t.Fatal("compiled descriptor verification census", logs)
					}
					raw, e := os.ReadFile(filepath.Join("..", "..", "benchmarks", "lexerpreparedinput", "input.json"))
					if e != nil {
						t.Fatal(e)
					}
					var table struct {
						Bindings map[string]int `json:"bindings"`
					}
					if e = json.Unmarshal(raw, &table); e != nil {
						t.Fatal(e)
					}
					for number := range table.Bindings {
						marker := fmt.Sprintf("LEXER_PREPARED_VERIFY id=%s bytes=512 match=1", number)
						if strings.Count(logs, marker+"\n") != 1 {
							t.Fatalf("missing/duplicate %s", marker)
						}
					}

				} else if strings.Contains(logs, "LEXER_PREPARED_VERIFY") {
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
