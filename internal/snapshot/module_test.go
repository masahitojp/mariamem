package snapshot

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestModuleBuildVerifiedDigest(t *testing.T) {
	module := filepath.Join(t.TempDir(), "guest.wasmu")
	if err := os.WriteFile(module, []byte("verified bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	digest, err := Digest(module)
	if err != nil {
		t.Fatal(err)
	}
	wasm := strings.Repeat("a", 64)
	for _, tc := range []struct {
		name, hash, build string
		version           int
		ok                bool
	}{
		{"valid", digest, wasm, 1, true},
		{"changed AOT identity", strings.Repeat("b", 64), wasm, 1, false},
		{"invalid WASM identity", digest, "bad", 1, false},
		{"stale snapshot protocol", digest, wasm, 2, false},
		{"empty digest", "", wasm, 1, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw, _ := json.Marshal(map[string]any{"module_sha256": digest, "wasm_sha256": tc.build, "snapshot_version": tc.version})
			if err := os.WriteFile(module+".json", raw, 0600); err != nil {
				t.Fatal(err)
			}
			build, err := ModuleBuildWithDigest(module, tc.hash)
			if (err == nil) != tc.ok || tc.ok && build != wasm {
				t.Fatalf("%s %v", build, err)
			}
		})
	}
	if err := os.Remove(module + ".json"); err != nil {
		t.Fatal(err)
	}
	if _, err := ModuleBuildWithDigest(module, digest); err == nil {
		t.Fatal("missing metadata accepted")
	}
}
