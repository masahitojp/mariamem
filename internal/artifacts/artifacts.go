// Package artifacts validates the existing native bundle for Go callers.
package artifacts

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"mariamem/internal/snapshot"
)

type Bundle struct{ Dir, Runtime, Module, Build string }

func Resolve(dir string) (Bundle, error) {
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		return Bundle{}, fmt.Errorf("mariamem requires darwin-arm64")
	}
	output, err := exec.Command("/usr/bin/sw_vers", "-productVersion").Output()
	if err != nil {
		return Bundle{}, err
	}
	major, err := strconv.Atoi(strings.Split(strings.TrimSpace(string(output)), ".")[0])
	if err != nil {
		return Bundle{}, err
	}
	return resolve(dir, "darwin-arm64", major)
}

func resolve(dir, platform string, major int) (Bundle, error) {
	var b Bundle
	if dir == "" {
		return b, fmt.Errorf("NativeDir is required")
	}
	root, err := filepath.Abs(dir)
	if err != nil {
		return b, err
	}
	var m struct {
		Version  int               `json:"version"`
		Platform string            `json:"platform"`
		Minimum  int               `json:"minimum_macos"`
		Hashes   map[string]string `json:"sha256"`
	}
	raw, err := os.ReadFile(filepath.Join(root, "manifest.json"))
	if err != nil {
		return b, err
	}
	if err = json.Unmarshal(raw, &m); err != nil {
		return b, err
	}
	if m.Version != 1 || m.Platform != platform || platform != "darwin-arm64" || m.Minimum <= 0 || major < m.Minimum {
		return b, fmt.Errorf("unsupported native bundle version/platform/minimum macOS")
	}
	// mariamem-host may be present in the unchanged bundle, but is not used by Go.
	for _, name := range []string{"wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"} {
		path := filepath.Join(root, name)
		info, err := os.Lstat(path)
		if err != nil {
			return b, err
		}
		if !info.Mode().IsRegular() {
			return b, fmt.Errorf("artifact must be a regular file: %s", name)
		}
		if name == "wasmer-headless" && info.Mode()&0111 == 0 {
			return b, fmt.Errorf("runtime is not executable")
		}
		hash, err := snapshot.Digest(path)
		if err != nil {
			return b, err
		}
		if hash != m.Hashes[name] {
			return b, fmt.Errorf("artifact hash mismatch: %s", name)
		}
	}
	b = Bundle{Dir: root, Runtime: filepath.Join(root, "wasmer-headless"), Module: filepath.Join(root, "mariamem.wasmu")}
	b.Build, err = snapshot.ModuleBuild(b.Module)
	return b, err
}
