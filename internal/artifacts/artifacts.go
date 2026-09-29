// Package artifacts validates the existing native bundle for Go callers.
package artifacts

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

type Bundle struct {
	Dir, Runtime, Module, Build string
	verified                    *startupIdentity
}

func Resolve(dir string) (Bundle, error) { return ResolveTimed(context.Background(), dir) }
func ResolveTimed(ctx context.Context, dir string) (Bundle, error) {
	ctx, finish := timing.Begin(ctx, "native_verification")
	defer finish()
	platform, major, err := currentTarget(ctx)
	if err != nil {
		return Bundle{}, err
	}
	timing.Mark(ctx, "platform_checked")
	return resolveTimed(ctx, dir, platform, major)
}

func currentTarget(ctx context.Context) (string, int, error) {
	if runtime.GOOS == "linux" && runtime.GOARCH == "amd64" {
		raw, err := os.ReadFile("/etc/os-release")
		if err != nil {
			return "", 0, diagnostic.Wrap("unsupported_platform", "platform", err)
		}
		if err := ubuntuPlatform(string(raw)); err != nil {
			return "", 0, err
		}
		return "ubuntu24.04-x86_64", 0, nil
	}
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("mariamem requires macOS 15+ arm64 or Ubuntu 24.04 x86_64; got %s-%s. Run on a supported platform with its matching native bundle", runtime.GOOS, runtime.GOARCH))
	}
	output, err := exec.CommandContext(ctx, "/usr/bin/sw_vers", "-productVersion").Output()
	if err != nil {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", err)
	}
	major, err := strconv.Atoi(strings.Split(strings.TrimSpace(string(output)), ".")[0])
	if err != nil {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", err)
	}
	return "darwin-arm64", major, nil
}

func ubuntuPlatform(raw string) error {
	values := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		key, value, ok := strings.Cut(line, "=")
		if ok {
			values[key] = strings.Trim(value, "\"'")
		}
	}
	if values["ID"] != "ubuntu" || values["VERSION_ID"] != "24.04" {
		return diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("requires Ubuntu 24.04 x86_64; got ID=%q VERSION_ID=%q. Run on a supported platform with its matching native bundle", values["ID"], values["VERSION_ID"]))
	}
	return nil
}

func resolve(dir, platform string, major int) (Bundle, error) {
	return resolveTimed(context.Background(), dir, platform, major)
}
func resolveTimed(ctx context.Context, dir, platform string, major int) (b Bundle, err error) {
	defer func() {
		if err != nil {
			var classified *diagnostic.Error
			if !errors.As(err, &classified) {
				code := "artifact_mismatch"
				if errors.Is(err, os.ErrNotExist) || errors.Is(err, os.ErrPermission) {
					code = "native_unavailable"
				}
				err = diagnostic.Wrap(code, "artifact_validation", fmt.Errorf("native bundle %q could not be validated; extract a complete matching release bundle and set Options.NativeDir to its directory: %w", dir, err))
			}
		}
	}()
	if platform != "darwin-arm64" && platform != "ubuntu24.04-x86_64" {
		return b, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("unsupported platform: %s", platform))
	}
	if dir == "" {
		return b, diagnostic.Wrap("native_unavailable", "artifact_validation", fmt.Errorf("NativeDir is required; download and extract the native bundle for your platform, then set Options.NativeDir to the extracted directory"))
	}
	root, err := filepath.Abs(dir)
	if err != nil {
		return b, err
	}
	var m struct {
		Version      int               `json:"version"`
		Platform     string            `json:"platform"`
		Minimum      int               `json:"minimum_macos"`
		Hashes       map[string]string `json:"sha256"`
		Distribution string            `json:"distribution"`
		VersionID    string            `json:"version_id"`
		Architecture string            `json:"architecture"`
	}
	identity, err := captureIdentity(root)
	if err != nil {
		return b, err
	}
	timing.Work(ctx, "identity_captured", 0, 4)
	raw, err := os.ReadFile(filepath.Join(root, "manifest.json"))
	if err != nil {
		return b, err
	}
	timing.Work(ctx, "manifest_read", int64(len(raw)), 1)
	if err = json.Unmarshal(raw, &m); err != nil {
		return b, err
	}
	if platform == "darwin-arm64" && m.Minimum > 0 && major < m.Minimum {
		return b, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("requires macOS %d or newer; got %d. Upgrade macOS or use another supported platform", m.Minimum, major))
	}
	if m.Version != 1 || m.Platform != platform {
		return b, fmt.Errorf("native manifest expected format 1 and platform %q; got format %d and platform %q", platform, m.Version, m.Platform)
	}
	if platform == "darwin-arm64" && m.Minimum <= 0 {
		return b, fmt.Errorf("unsupported native bundle minimum macOS")
	}
	if platform == "ubuntu24.04-x86_64" && (m.Distribution != "ubuntu" || m.VersionID != "24.04" || m.Architecture != "x86_64") {
		return b, fmt.Errorf("native bundle requires Ubuntu 24.04 x86_64 metadata; got distribution=%q version_id=%q architecture=%q", m.Distribution, m.VersionID, m.Architecture)
	}
	timing.Mark(ctx, "manifest_checked")
	// mariamem-host may be present in the unchanged bundle, but is not used by Go.
	names := []string{"wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"}
	err = snapshot.VerifyIndependent(len(names), func(i int) error {
		name := names[i]
		path := filepath.Join(root, name)
		info, err := os.Lstat(path)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("artifact must be a regular file: %s", name)
		}
		if name == "wasmer-headless" && info.Mode()&0111 == 0 {
			return diagnostic.Wrap("native_unavailable", "artifact_validation", fmt.Errorf("runtime is not executable: %s; re-extract the native bundle preserving executable permissions", path))
		}
		timing.Work(ctx, name+"/metadata", 0, 1)
		hash, err := snapshot.DigestTimed(ctx, path, name)
		if err != nil {
			return err
		}
		if hash != m.Hashes[name] {
			return fmt.Errorf("artifact hash mismatch: %s; expected SHA256 %q, got %q", path, m.Hashes[name], hash)
		}
		timing.Mark(ctx, name+"/hash_compared")
		return nil
	})
	if err != nil {
		return b, err
	}
	b = Bundle{Dir: root, Runtime: filepath.Join(root, "wasmer-headless"), Module: filepath.Join(root, "mariamem.wasmu")}
	b.Build, err = snapshot.ModuleBuildWithDigestTimed(ctx, b.Module, m.Hashes["mariamem.wasmu"])
	if err != nil {
		return b, err
	}
	timing.Mark(ctx, "sidecar_identity_checked")
	identity.build = b.Build
	b.verified = identity
	if _, err = b.CheckStartupIdentity(b.Runtime, b.Module); err != nil {
		return Bundle{}, err
	}
	timing.Work(ctx, "identity_rechecked", 0, 4)
	return b, nil
}
