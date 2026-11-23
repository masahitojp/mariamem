package artifacts

import (
	"fmt"
	"os"
	"runtime"
	"syscall"
	"unsafe"
)

func windowsTarget() (string, int, error) {
	var version struct {
		Size, Major, Minor, Build, Platform uint32
		CSD                                 [128]uint16
	}
	version.Size = uint32(unsafe.Sizeof(version))
	status, _, _ := syscall.NewLazyDLL("ntdll.dll").NewProc("RtlGetVersion").Call(uintptr(unsafe.Pointer(&version)))
	if int32(status) < 0 || version.Major < 10 || version.Major == 10 && version.Build < 22000 {
		return "", 0, fmt.Errorf("requires Windows build 22000+; got %d.%d build %d", version.Major, version.Minor, version.Build)
	}
	arch := map[string]string{"amd64": "x86_64", "arm64": "arm64"}[runtime.GOARCH]
	if arch == "" || os.Getpagesize() <= 0 || 65536%os.Getpagesize() != 0 {
		return "", 0, fmt.Errorf("unsupported Windows CPU/page size: %s/%d", runtime.GOARCH, os.Getpagesize())
	}
	return "windows-" + arch, int(version.Build), nil
}
