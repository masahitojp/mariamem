package artifacts

import (
	"encoding/json"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	write := func(name string, b []byte, mode os.FileMode) {
		t.Helper()
		if err := os.WriteFile(filepath.Join(dir, name), b, mode); err != nil {
			t.Fatal(err)
		}
	}
	write("wasmer-headless", []byte("runtime fixture, never executed"), 0700)
	write("mariamem.wasmu", []byte("guest fixture, never executed"), 0600)
	hash, _ := snapshot.Digest(filepath.Join(dir, "mariamem.wasmu"))
	sidecar, _ := json.Marshal(map[string]any{"wasm_sha256": strings.Repeat("a", 64), "module_sha256": hash, "snapshot_version": 1})
	write("mariamem.wasmu.json", sidecar, 0600)
	hashes := map[string]string{}
	for _, name := range []string{"wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"} {
		hashes[name], _ = snapshot.Digest(filepath.Join(dir, name))
	}
	manifest, _ := json.Marshal(map[string]any{"version": 1, "platform": "darwin-arm64", "minimum_macos": 15, "sha256": hashes, "public_release_ready": false})
	write("manifest.json", manifest, 0600)
	// Existing bundle's host is deliberately unused by Go.
	write("mariamem-host", []byte("unused"), 0600)
	return dir
}
func TestResolveBundle(t *testing.T) {
	dir := fixture(t)
	b, err := resolve(dir, "darwin-arm64", 15)
	if err != nil || b.Dir != dir || b.Build != strings.Repeat("a", 64) {
		t.Fatalf("%+v %v", b, err)
	}
	for _, tc := range []struct {
		platform string
		major    int
	}{{"linux-arm64", 15}, {"darwin-amd64", 15}, {"darwin-arm64", 12}, {"darwin-arm64", 13}, {"darwin-arm64", 14}} {
		if _, err := resolve(dir, tc.platform, tc.major); err == nil {
			t.Fatal("incompatible platform accepted")
		}
	}
	if _, err := resolve("", "darwin-arm64", 15); err == nil {
		t.Fatal("missing directory accepted")
	}
}
func TestInvalidBundle(t *testing.T) {
	for _, kind := range []string{"hash", "missing", "executable", "symlink", "sidecar", "version", "missing-hash", "minimum"} {
		t.Run(kind, func(t *testing.T) {
			dir := fixture(t)
			module := filepath.Join(dir, "mariamem.wasmu")
			switch kind {
			case "hash":
				os.WriteFile(module, []byte("changed"), 0600)
			case "missing":
				os.Remove(module)
			case "executable":
				os.Chmod(filepath.Join(dir, "wasmer-headless"), 0600)
			case "symlink":
				os.Rename(module, module+".real")
				os.Symlink(module+".real", module)
			default:
				path := filepath.Join(dir, "manifest.json")
				raw, _ := os.ReadFile(path)
				var m map[string]any
				json.Unmarshal(raw, &m)
				switch kind {
				case "sidecar":
					p := module + ".json"
					os.WriteFile(p, []byte(`{"snapshot_version":1,"wasm_sha256":"bad","module_sha256":"bad"}`), 0600)
					h, _ := snapshot.Digest(p)
					m["sha256"].(map[string]any)["mariamem.wasmu.json"] = h
				case "version":
					m["version"] = 2
				case "missing-hash":
					delete(m["sha256"].(map[string]any), "mariamem.wasmu")
				case "minimum":
					m["minimum_macos"] = 0
				}
				raw, _ = json.Marshal(m)
				os.WriteFile(path, raw, 0600)
			}
			if _, err := resolve(dir, "darwin-arm64", 15); err == nil {
				t.Fatal("invalid bundle accepted")
			}
		})
	}
}
