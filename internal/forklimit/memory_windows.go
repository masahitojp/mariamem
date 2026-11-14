package forklimit

import (
	"syscall"
	"unsafe"
)

func memoryLimits() []uint64 {
	kernel := syscall.NewLazyDLL("kernel32.dll")
	var state struct {
		Length, Load                                                                                         uint32
		TotalPhys, AvailPhys, TotalPageFile, AvailPageFile, TotalVirtual, AvailVirtual, AvailExtendedVirtual uint64
	}
	state.Length = uint32(unsafe.Sizeof(state))
	var limits []uint64
	ok, _, _ := kernel.NewProc("GlobalMemoryStatusEx").Call(uintptr(unsafe.Pointer(&state)))
	if ok != 0 {
		if n := memoryBytes(state.TotalPhys, 1); n > 0 {
			limits = append(limits, n)
		}
	}
	// Observe the current job's declared process/job limits when available.
	// As with hidden cgroups, inaccessible ancestor limits are not a guarantee.
	var job struct {
		ProcessTime, JobTime                                                 int64
		Flags                                                                uint32
		MinWorkingSet, MaxWorkingSet                                         uintptr
		ActiveProcessLimit                                                   uint32
		Affinity                                                             uintptr
		PriorityClass, SchedulingClass                                       uint32
		IOCounters                                                           [6]uint64
		ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemory, PeakJobMemory uintptr
	}
	// Query the current job with the native 64-bit Windows ABI layout.
	ok, _, _ = kernel.NewProc("QueryInformationJobObject").Call(0, 9, uintptr(unsafe.Pointer(&job)), unsafe.Sizeof(job), 0)
	if ok != 0 {
		if job.Flags&0x100 != 0 {
			if n := memoryBytes(uint64(job.ProcessMemoryLimit), 1); n > 0 {
				limits = append(limits, n)
			}
		}
		if job.Flags&0x200 != 0 {
			if n := memoryBytes(uint64(job.JobMemoryLimit), 1); n > 0 {
				limits = append(limits, n)
			}
		}
	}
	return limits
}
