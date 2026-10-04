//go:build experiment_mmap && ((darwin && arm64) || (linux && amd64))

package generatedgo

import (
	"encoding/binary"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"sync/atomic"
	"syscall"
	"testing"
	"time"
	"unsafe"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
)

func experimentTestHost() *host {
	return &host{WasiStubs: base.DefaultWASI(), fdFlags: map[int32]uint16{}}
}

func TestExperimentMmapContract(t *testing.T) {
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	m, release, err := experimentMappedModule(experimentTestHost())
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	runtime.ReadMemStats(&after)
	if after.TotalAlloc-before.TotalAlloc > 64<<20 {
		t.Fatal("large Go allocation", after.TotalAlloc-before.TotalAlloc)
	}
	ptr := m.M
	if len(m.Memory) != experimentMaximum || cap(m.Memory) != experimentMaximum || m.MaxMem != experimentMaximum || base.MemorySize(m) != 4096 || uintptr(ptr)%uintptr(os.Getpagesize()) != 0 {
		t.Fatal("initial contract")
	}
	if base.MemoryGrow(m, 0) != 4096 || base.MemoryGrow(m, -1) != -1 {
		t.Fatal("grow zero/huge")
	}
	// Real generated scalar load, data/TLS initializer, and scalar store function.
	p8.Fn66(m, 65536)
	binary.LittleEndian.PutUint32(m.Memory[65540:], 123)
	if p8.Fn68(m) != 123 || p8.Fn80(m, 0, 131072) != 0 {
		t.Fatal("generated load/store")
	}
	if binary.LittleEndian.Uint64(m.Memory[131072:]) == 0 {
		t.Fatal("generated timespec store")
	}
	oldCommit := m.ExperimentMemoryCommit
	m.ExperimentMemoryCommit = func(uint64, uint64) error { return syscall.ENOMEM }
	if base.MemoryGrow(m, 1) != -1 || base.MemorySize(m) != 4096 {
		t.Fatal("failed protection published size")
	}
	m.ExperimentMemoryCommit = oldCommit
	if base.MemoryGrow(m, 1) != 4096 || m.M != ptr || m.Memory[generated.InitialMemoryBytes] != 0 {
		t.Fatal("first grow")
	}
	word := base.AtomicPtr32At(m, generated.InitialMemoryBytes+1024)
	atomic.StoreUint32(word, 0)
	m.G0 = 8 << 20
	parentTLS := m.G1
	results := make(chan bool, 1)
	base.ThreadLaunch(m, func(child *base.Module, tid int32) {
		p8.Fn66(child, generated.InitialMemoryBytes)
		binary.LittleEndian.PutUint32(child.Memory[generated.InitialMemoryBytes+4:], 456)
		ok := child.M == ptr && child.MemSize == m.MemSize && p8.Fn68(child) == 456
		child.G0 = 7 << 20
		atomic.StoreUint32(base.AtomicPtr32At(child, generated.InitialMemoryBytes+1024), 99)
		results <- ok
	})
	base.SpikeWait(m)
	if !<-results || atomic.LoadUint32(word) != 99 || m.G1 != parentTLS || m.G0 != 8<<20 || p8.Fn68(m) != 123 {
		t.Fatal("worker shared visibility / private stack and TLS global")
	}
	if base.MemoryGrow(m, 32768-4097) != 4097 || base.MemorySize(m) != 32768 || m.M != ptr || m.Memory[experimentMaximum-1] != 0 || p8.Fn68(m) != 123 {
		t.Fatal("full maximum grow, zero/preservation/stability")
	}
	if p8.Fn80(m, 0, experimentMaximum-65536) != 0 {
		t.Fatal("generated store near maximum")
	}
	if base.MemoryGrow(m, 1) != -1 {
		t.Fatal("beyond max")
	}
	// Bounds/alignment checks remain the actual shared Module helpers.
	func() {
		defer func() {
			if recover() == nil {
				t.Error("unaligned atomic did not reject")
			}
		}()
		base.AtomicEA(m, 3, 0, 4)
	}()
	func() {
		defer func() {
			if recover() == nil {
				t.Error("out of bounds atomic did not reject")
			}
		}()
		base.AtomicEA(m, -2147483648, 0, 4)
	}()
	old := m.Memory
	if err = release(); err != nil {
		t.Fatal(err)
	}
	if err = release(); err != nil {
		t.Fatal("idempotent release", err)
	}
	if ExperimentMappingStats()["active_mappings"] != 0 {
		t.Fatal("mapping retained")
	}
	// Asking the OS to protect a now-unmapped address must fail. No byte access.
	if err = syscall.Mprotect(old[:os.Getpagesize()], syscall.PROT_NONE); err == nil {
		t.Fatal("OS mapping still present after munmap")
	}
	runtime.KeepAlive(m)
	t.Logf("contract PASS, Go constructor TotalAlloc delta=%d; OS unmap returned %v; counters=%v", after.TotalAlloc-before.TotalAlloc, err, ExperimentMappingStats())
}

func TestExperimentMmapWorkerGrowAndFutex(t *testing.T) {
	h := experimentTestHost()
	m, release, err := experimentMappedModule(h)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	const addr, timeout, result, woke = 64, 80, 96, 97
	word := base.AtomicPtr32At(m, addr)
	atomic.StoreUint32(word, 2)
	m.Memory[timeout] = 1
	binary.LittleEndian.PutUint64(m.Memory[timeout+8:], uint64(20*time.Millisecond))
	if h.Futex_wake(m, addr, woke) != 0 || h.Futex_wait(m, addr, 2, timeout, result) != 0 || m.Memory[result] != 0 {
		t.Fatal("empty wake stores no permit / timeout")
	}
	atomic.StoreUint32(word, 0)
	if h.Futex_wait(m, addr, 2, timeout, result) != 0 || m.Memory[result] != 1 {
		t.Fatal("futex mismatch")
	}
	done := make(chan error, 1)
	base.ThreadLaunch(m, func(child *base.Module, tid int32) {
		if base.MemoryGrow(child, 1) != 4096 {
			done <- syscall.EINVAL
			return
		}
		child.Memory[generated.InitialMemoryBytes] = 7
		done <- nil
	})
	base.SpikeWait(m)
	if err = <-done; err != nil || base.MemorySize(m) != 4097 || m.Memory[generated.InitialMemoryBytes] != 7 {
		t.Fatal("worker grow not visible", err)
	}
	// Exercise actual host wait registration and wake, with a changed barrier.
	binary.LittleEndian.PutUint64(m.Memory[timeout+8:], uint64(time.Second))
	atomic.StoreUint32(word, 2)
	waiting := make(chan struct{})
	base.ThreadLaunch(m, func(child *base.Module, tid int32) { close(waiting); h.Futex_wait(child, addr, 2, timeout, result) })
	<-waiting
	atomic.StoreUint32(word, 0)
	if h.Futex_wake(m, addr, woke) != 0 {
		t.Fatal("wake ABI")
	}
	base.SpikeWait(m)
	if m.Memory[result] != 1 {
		t.Fatal("wait/wake")
	}
}

func TestExperimentMmapInaccessibleTail(t *testing.T) {
	if os.Getenv("MARIAMEM_MMAP_TAIL_PROBE") == "1" {
		b, err := experimentReserve()
		if err != nil {
			panic(err)
		}
		// Deliberate illegal raw load in a disposable subprocess. Expected fatal
		// protection fault, not a claimed recoverable WASM trap implementation.
		v := *(*byte)(unsafe.Add(unsafe.Pointer(unsafe.SliceData(b.memory)), generated.InitialMemoryBytes))
		os.Exit(int(v))
	}
	cmd := exec.Command(os.Args[0], "-test.run=^TestExperimentMmapInaccessibleTail$")
	cmd.Env = append(os.Environ(), "MARIAMEM_MMAP_TAIL_PROBE=1")
	text, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(text), "fault") {
		t.Fatalf("tail was not protected: %v %s", err, text)
	}
	t.Log("OS protects tail; no generated bounds/signal handler redesign")
}
