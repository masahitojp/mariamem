//go:build integration

package generatedgo

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// The private switch is supplied at construction, never by guestEnvironment or
// the public API. Run this only against the newly generated prepared-table guest.
func TestUCACopyActualGuest(t *testing.T) {
	t.Setenv("MARIAMEM_UCA_COPY_VERIFY_INTERNAL", "1")
	for _, tc := range []struct {
		name                            string
		verify, timing, corrupt, reject bool
	}{
		{"normal_ambient_ignored", false, false, false, false},
		{"profiling_does_not_verify", false, true, false, false},
		{"fifteen_default_levels", true, false, false, false},
		{"corruption_without_verifier", false, false, true, false},
		{"corrupt_table_rejected", true, false, true, true},
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
				queries := make([]string, 0, 5)
				for _, encoding := range []string{"utf8mb3", "utf8mb4", "ucs2", "utf16", "utf32"} {
					queries = append(queries, fmt.Sprintf("SELECT STRCMP(CONVERT(_utf8mb4'a' USING %s) COLLATE %s_uca1400_ai_ci,CONVERT(_utf8mb4'A' USING %s) COLLATE %s_uca1400_ai_ci)", encoding, encoding, encoding, encoding))
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
					h.SetEnv(append(wireGuestEnvironment(false, tc.timing), "MARIAMEM_CONTROL_EPOCH=1", "MARIAMEM_UCA_COPY_VERIFY_INTERNAL=1"))
				}
				m, release, err := newMemoryModule(h)
				if err == nil && tc.corrupt {
					// Exact canonical flag table in this guest, not an inferred match.
					const address = 10148368
					const size = 12288
					if fmt.Sprintf("%x", sha256.Sum256(m.Memory[address:address+size])) != "ef290f39feb57991e9871bbc5d58d78f8e42e6db73c477f25920493cebba6a0f" {
						release()
						return nil, nil, fmt.Errorf("canonical flags input mismatch")
					}
					m.Memory[address+37] ^= 1

				}
				return m, release, err
			}
			done := startWireInstance(childIn, childOut, &diagnostic, "", nil, tc.timing, nil, construct, 1, &WireLifecycle{Capture: &prepared.Capture{}, Approval: make(chan error, 1)})
			select {
			case err = <-done:
			case <-time.After(30 * time.Second):
				t.Fatal("guest did not terminate")
			}
			if tc.reject {
				if err == nil {
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
					for _, id := range []int{2048, 2304, 2560, 2816, 3072} {
						for level := 0; level < 3; level++ {
							marker := fmt.Sprintf("UCA_COPY_VERIFY id=%d level=%d match=1", id, level)
							if !strings.Contains(logs, marker) {
								t.Fatalf("missing %s: %s", marker, logs)
							}
						}
					}
				} else if strings.Contains(logs, "UCA_COPY_VERIFY") {
					t.Fatal("ordinary execution performed verification", logs)
				}
			}
			input.Close()
			output.Close()
			childIn.Close()
			childOut.Close()
			if tc.reject {
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
