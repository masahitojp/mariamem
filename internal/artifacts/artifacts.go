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
		return "", 0, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("mariamem requires macOS 15+ arm64 or Ubuntu 24.04 x86_64; got %s-%s. Run on a supported platform with its matching generated-Go package", runtime.GOOS, runtime.GOARCH))
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

func ubuntuPlatform(raw string) error {
	values := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		key, value, ok := strings.Cut(line, "=")
		if ok {
			values[key] = strings.Trim(value, "\"'")
		}
	}
	if values["ID"] != "ubuntu" || values["VERSION_ID"] != "24.04" {
		return diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("requires Ubuntu 24.04 x86_64; got ID=%q VERSION_ID=%q. Run on a supported platform with its matching generated-Go package", values["ID"], values["VERSION_ID"]))
	}
	return nil
}
