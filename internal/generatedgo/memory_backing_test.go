//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"context"
	"encoding/binary"
	"io"
	"os"
	"runtime"
	"strings"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
)

func mappedTestHost() *host {
	return &host{WasiStubs: base.DefaultWASI(), fdFlags: map[int32]uint16{}}
}

func TestMappedMemoryContract(t *testing.T) {
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	m, release, err := newMemoryModule(mappedTestHost())
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	runtime.ReadMemStats(&after)
	if after.TotalAlloc-before.TotalAlloc > 64<<20 {
		t.Fatal("large Go allocation", after.TotalAlloc-before.TotalAlloc)
	}
	ptr := m.M
	if len(m.Memory) != (2<<30) || cap(m.Memory) != (2<<30) || m.MaxMem != (2<<30) || base.MemorySize(m) != 4096 || uintptr(ptr)%uintptr(os.Getpagesize()) != 0 {
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
	oldCommit := m.PrepareMemoryGrow
	m.PrepareMemoryGrow = func(uint64, uint64) error { return syscall.ENOMEM }
	if base.MemoryGrow(m, 1) != -1 || base.MemorySize(m) != 4096 {
		t.Fatal("failed protection published size")
	}
	m.PrepareMemoryGrow = oldCommit
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
	if base.MemoryGrow(m, 32768-4097) != 4097 || base.MemorySize(m) != 32768 || m.M != ptr || m.Memory[(2<<30)-1] != 0 || p8.Fn68(m) != 123 {
		t.Fatal("full maximum grow, zero/preservation/stability")
	}
	if p8.Fn80(m, 0, (2<<30)-65536) != 0 {
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
	if base.MemoryMappingStats()["active_mappings"] != 0 {
		t.Fatal("mapping retained")
	}
	// Asking the OS to protect a now-unmapped address must fail. No byte access.
	if err = syscall.Mprotect(old[:os.Getpagesize()], syscall.PROT_NONE); err == nil {
		t.Fatal("OS mapping still present after munmap")
	}
	runtime.KeepAlive(m)
	t.Logf("contract PASS, Go constructor TotalAlloc delta=%d; post-unmap protection probe returned %v; counters=%v", after.TotalAlloc-before.TotalAlloc, err, base.MemoryMappingStats())
}

func TestMappedMemoryWorkerGrowAndFutex(t *testing.T) {
	h := mappedTestHost()
	m, release, err := newMemoryModule(h)
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

func TestMappedMemoryInitializationFailure(t *testing.T) {
	before := base.MemoryMappingStats()
	func() {
		defer func() {
			if recover() == nil {
				t.Error("expected constructor panic")
			}
		}()
		_, _, _ = initializeMemoryModule(func() (*base.MemoryMapping, error) { return base.NewMemoryMapping(65536, 3*65536) }, func(*base.MemoryMapping) *base.Module { panic("injected partial initialization") })
	}()
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"] != before["releases"]+1 {
		t.Fatal("partial initialization leaked", before, after)
	}
	for i := 0; i < 3; i++ {
		// Restore failure occurs before reserve; missing prepared source must not leak.
		if err := <-StartInstance(context.Background(), strings.NewReader(""), io.Discard, io.Discard, "", t.TempDir()+"/missing", false); err == nil {
			t.Fatal("expected failed restore")
		}
	}
	if base.MemoryMappingStats()["active_mappings"] != before["active_mappings"] {
		t.Fatal("failed start leaked")
	}
}

func TestMappedMemoryFailedExecutionJoinsBeforeRelease(t *testing.T) {
	before := base.MemoryMappingStats()
	m, release, err := newMemoryModule(mappedTestHost())
	if err != nil {
		t.Fatal(err)
	}
	entered, unblock, done := make(chan struct{}), make(chan struct{}), make(chan error, 1)
	go func() {
		var result error
		defer func() { done <- result }()
		defer releaseMemoryModule(m, release, &result)
		result = executeGuest(m, func(m *base.Module) {
			base.ThreadLaunch(m, func(child *base.Module, tid int32) { close(entered); <-unblock; child.Memory[64] = 9 })
			panic("injected startup failure after worker start")
		})
	}()
	<-entered
	select {
	case <-done:
		t.Fatal("released before worker join")
	default:
	}
	if base.MemoryMappingStats()["active_mappings"] != before["active_mappings"]+1 {
		t.Fatal("early release")
	}
	close(unblock)
	if e := <-done; e == nil || !strings.Contains(e.Error(), "startup failure") {
		t.Fatal("failure lost", e)
	}
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"] != before["releases"]+1 {
		t.Fatal("failed execution leak", before, after)
	}
	if err := release(); err != nil {
		t.Fatal(err)
	}
	if base.MemoryMappingStats()["releases"] != after["releases"] {
		t.Fatal("double release")
	}
}
