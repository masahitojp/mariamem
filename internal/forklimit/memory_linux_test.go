package forklimit

import (
	"slices"
	"syscall"
	"testing"
)

func TestLinuxKernelTotalRAMIsAnObservedLimit(t *testing.T) {
	var info syscall.Sysinfo_t
	if err := syscall.Sysinfo(&info); err != nil {
		t.Skipf("sysinfo unavailable on this host: %v; injected failure cases still run", err)
	}
	total, unit, err := kernelRAM()
	if err != nil || total != uint64(info.Totalram) || unit != uint64(info.Unit) {
		t.Fatal("sysinfo adapter did not return kernel totalram/mem_unit", total, unit, err)
	}
	want := memoryBytes(uint64(info.Totalram), uint64(info.Unit))
	if want == 0 {
		t.Fatal("kernel returned invalid totalram/mem_unit", info.Totalram, info.Unit)
	}
	limits := memoryLimits()
	if !slices.Contains(limits, want) {
		t.Fatalf("kernel total %d missing from observed limits %v", want, limits)
	}
}
