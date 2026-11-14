// Package artifacts checks the generated-Go supported-platform contract.
package artifacts

import (
	"context"
	"fmt"
	"github.com/masahitojp/mariamem/internal/diagnostic"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
)

// Successful macOS detection is process-local. A new process checks again;
// changes to sw_vers after success are deliberately not re-detected.
var macOSPlatform = platformCheck{probe: checkMacOS}

// ValidatePlatform checks the supported OS/architecture. Only successful macOS
// checks are reused; Linux detection and failed checks are not cached.
func ValidatePlatform(ctx context.Context) error {
	if runtime.GOOS == "darwin" && runtime.GOARCH == "arm64" {
		return macOSPlatform.validate(ctx)
	}
	_, _, err := currentTarget(ctx)
	return err
}

func currentTarget(ctx context.Context) (string, int, error) {
	if runtime.GOOS == "linux" {
		if err := platformContextError(ctx); err != nil {
			return "", 0, err
		}
		return linuxTarget(runtime.GOARCH, os.Getpagesize())
	}
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("mariamem requires macOS 15+ arm64 or Linux x86_64/aarch64; got %s-%s. Run on a supported platform with its matching generated-Go package", runtime.GOOS, runtime.GOARCH))
	}
	return readMacOS(ctx)
}

func readMacOS(ctx context.Context) (string, int, error) {
	output, err := exec.CommandContext(ctx, "/usr/bin/sw_vers", "-productVersion").Output()
	if err != nil {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", err)
	}
	major, err := macOSMajor(string(output))
	if err != nil {
		return "", 0, err
	}
	return "darwin-arm64", major, nil
}

func macOSMajor(output string) (int, error) {
	major, err := strconv.Atoi(strings.Split(strings.TrimSpace(output), ".")[0])
	if err != nil {
		return 0, diagnostic.Wrap("unsupported_platform", "platform", err)
	}
	if major < 15 {
		return 0, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("requires macOS15+ arm64"))
	}
	return major, nil
}

func checkMacOS(ctx context.Context) error {
	_, _, err := readMacOS(ctx)
	return err
}

// The generated-Go host is static and uses kernel syscalls, not a libc ABI.
// Python wheel discovery separately enforces its interpreter/libc tag minimums.
func linuxTarget(arch string, pageSize int) (string, int, error) {
	identity := map[string]string{"amd64": "linux-x86_64", "arm64": "linux-aarch64"}[arch]
	if identity == "" || pageSize <= 0 || pageSize > 65536 || 65536%pageSize != 0 {
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf(
			"requires Linux x86_64/aarch64 with a page size dividing 65536; got arch=%s page_size=%d", arch, pageSize))
	}
	return identity, 0, nil
}
