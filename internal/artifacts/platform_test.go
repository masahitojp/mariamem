package artifacts

import (
	"context"
	"runtime"
	"testing"
)

func TestLinuxPlatformConditions(t *testing.T) {
	for arch, want := range map[string]string{"amd64": "linux-x86_64", "arm64": "linux-aarch64"} {
		for _, page := range []int{4096, 16384, 65536} {
			got, _, err := linuxTarget(arch, page)
			if err != nil || got != want {
				t.Fatalf("%s/%d: %s %v", arch, page, got, err)
			}
		}
	}
	for _, bad := range []struct {
		arch string
		page int
	}{
		{"386", 4096}, {"riscv64", 4096}, {"arm64", 0}, {"amd64", -4096}, {"arm64", 81920}, {"amd64", 6000},
	} {
		if _, _, err := linuxTarget(bad.arch, bad.page); err == nil {
			t.Fatalf("accepted unsupported platform: %+v", bad)
		}
	}
}

func TestLinuxProductionPlatform(t *testing.T) {
	if runtime.GOOS != "linux" || (runtime.GOARCH != "amd64" && runtime.GOARCH != "arm64") {
		t.Skip("native Linux check")
	}
	if err := ValidatePlatform(context.Background()); err != nil {
		t.Fatal(err)
	}
	got, _, err := currentTarget(context.Background())
	want := map[string]string{"amd64": "linux-x86_64", "arm64": "linux-aarch64"}[runtime.GOARCH]
	if err != nil || got != want {
		t.Fatalf("production target: %s %v, want %s", got, err, want)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := ValidatePlatform(ctx); err == nil {
		t.Fatal("accepted cancelled platform check")
	}
}
