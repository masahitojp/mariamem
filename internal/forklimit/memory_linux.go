package forklimit

import (
	"os"
	"syscall"
)

func kernelRAM() (total, unit uint64, err error) {
	var info syscall.Sysinfo_t
	if err = syscall.Sysinfo(&info); err != nil {
		return 0, 0, err
	}
	return uint64(info.Totalram), uint64(info.Unit), nil
}

func memoryLimits() []uint64 {
	return linuxMemoryLimits(kernelRAM, os.ReadFile)
}
