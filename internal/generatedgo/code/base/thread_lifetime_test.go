package base

import (
	"encoding/binary"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"
)

func lifetimeModule() *Module {
	b := make([]byte, 65536)
	size := &atomic.Uint64{}
	size.Store(uint64(len(b)))
	m := &Module{Memory: b, M: unsafe.Pointer(&b[0]), MemSize: size, MemShared: true, Threads: &ThreadPool{}}
	ForceContendedAtomics(m)
	return m
}

func lifetimeArgs(m *Module, arg, td, ptr uint32) {
	binary.LittleEndian.PutUint32(m.Memory[arg+16:], td)
	binary.LittleEndian.PutUint32(m.Memory[td+40:], ptr)
	binary.LittleEndian.PutUint32(m.Memory[td+44:], 4096)
}

func lifetimeReceive[T any](t *testing.T, ch <-chan T) T {
	t.Helper()
	select {
	case v := <-ch:
		return v
	case <-time.After(2 * time.Second):
		t.Fatal("lifetime event did not complete")
		var zero T
		return zero
	}
}

func TestWorkerReclaimWaitsForLastAccess(t *testing.T) {
	m := lifetimeModule()
	const ptr = 4096
	lifetimeArgs(m, 256, 512, ptr)
	entered := make(chan struct{})
	stop := make(chan struct{})
	var release sync.Once
	t.Cleanup(func() { release.Do(func() { close(stop) }) })
	m.ThreadStart = func(child *Module, tid, arg int32) {
		defer func() { child.Memory[ptr+128] = 1 }() // final body defer is included
		close(entered)
		<-stop
	}
	freed := make(chan *Module, 1)
	InstallThreadLifetime(m, func(raw *Module, p int32) {
		if raw.ThreadLifetime != nil || p != ptr || raw.Memory[ptr+128] != 1 {
			t.Error("reclaimer ran before the last guest access or bypass is missing")
		}
		raw.Memory[ptr+128] = 165 // model immediate allocator reuse
		freed <- raw
	})
	if ThreadSpawn(m, 256) <= 0 {
		t.Fatal("spawn failed")
	}
	lifetimeReceive(t, entered)
	done := make(chan bool, 1)
	go func() { done <- DeferThreadAllocationFree(m, ptr) }()
	select {
	case <-freed:
		t.Fatal("allocation freed while worker was still active")
	case <-time.After(10 * time.Millisecond):
	}
	// Other allocations must remain usable while this join is blocked.
	if DeferThreadAllocationFree(m, ptr+16) {
		t.Fatal("unrelated free intercepted")
	}
	release.Do(func() { close(stop) })
	lifetimeReceive(t, freed)
	if !lifetimeReceive(t, done) || m.Threads.WaitThreads() != nil || m.Memory[ptr+128] != 165 {
		t.Fatal("completed reclaim/reuse failed")
	}
	if len(m.ThreadLifetime.maps) != 0 {
		t.Fatal("completed allocation retained")
	}
}

func TestDetachedSelfReclaimEndsBeforePoolCompletion(t *testing.T) {
	for _, how := range []string{"return", "goexit", "panic"} {
		t.Run(how, func(t *testing.T) {
			m := lifetimeModule()
			lifetimeArgs(m, 256, 512, 4096)
			var frees atomic.Int32
			m.ThreadStart = func(child *Module, tid, arg int32) {
				if !DeferThreadAllocationFree(child, 4096) {
					t.Error("self-free not deferred")
				}
				child.Memory[4224] = 1
				defer func() { child.Memory[4224] = 2 }()
				switch how {
				case "goexit":
					runtime.Goexit()
				case "panic":
					panic("owned-worker-failure")
				}
			}
			InstallThreadLifetime(m, func(raw *Module, ptr int32) {
				if raw.Memory[4224] != 2 || raw.ThreadLifetime != nil {
					t.Error("self reclamation preceded final defer")
				}
				raw.Memory[4224] = 165
				frees.Add(1)
			})
			ThreadSpawn(m, 256)
			trap := m.Threads.WaitThreads()
			if (trap != nil) != (how == "panic") || frees.Load() != 1 || m.Memory[4224] != 165 || len(m.ThreadLifetime.maps) != 0 {
				t.Fatalf("trap=%v frees=%d allocations=%d", trap, frees.Load(), len(m.ThreadLifetime.maps))
			}
		})
	}
}

func TestCompletedJoinAddressReuseAndIndependentDB(t *testing.T) {
	m := lifetimeModule()
	lifetimeArgs(m, 256, 512, 4096)
	var frees atomic.Int32
	m.ThreadStart = func(*Module, int32, int32) {}
	InstallThreadLifetime(m, func(*Module, int32) { frees.Add(1) })
	for i := 0; i < 32; i++ {
		ThreadSpawn(m, 256)
		if m.Threads.WaitThreads() != nil || !DeferThreadAllocationFree(m, 4096) || len(m.ThreadLifetime.maps) != 0 {
			t.Fatal("generation reclaim failed")
		}
	}
	other := lifetimeModule()
	other.ThreadStart = func(*Module, int32, int32) {}
	InstallThreadLifetime(other, func(*Module, int32) { t.Error("wrong DB reclaimer") })
	if DeferThreadAllocationFree(other, 4096) || frees.Load() != 32 {
		t.Fatal("allocation ownership crossed DBs")
	}
}

func TestConcurrentWorkerReclaims(t *testing.T) {
	m := lifetimeModule()
	const n = 8
	var frees atomic.Int32
	m.ThreadStart = func(child *Module, tid, arg int32) { runtime.Gosched() }
	InstallThreadLifetime(m, func(*Module, int32) { frees.Add(1) })
	var joins sync.WaitGroup
	for i := 0; i < n; i++ {
		arg, td, ptr := uint32(256+i*64), uint32(2048+i*64), uint32(8192+i*4096)
		lifetimeArgs(m, arg, td, ptr)
		ThreadSpawn(m, int32(arg))
		// A real join does not reach free before guest entry publishes exit.
		// Wait until registry publication to model that already-exited route.
		for {
			m.ThreadLifetime.mu.RLock()
			registered := m.ThreadLifetime.maps[ptr] != nil
			m.ThreadLifetime.mu.RUnlock()
			if registered {
				break
			}
			runtime.Gosched()
		}
		joins.Add(1)
		go func() { defer joins.Done(); DeferThreadAllocationFree(m, int32(ptr)) }()
	}
	joins.Wait()
	if m.Threads.WaitThreads() != nil || frees.Load() != n || len(m.ThreadLifetime.maps) != 0 {
		t.Fatal("parallel joins did not reclaim exactly once")
	}
}

func TestFailedSpawnDoesNotRegisterAllocation(t *testing.T) {
	m := lifetimeModule()
	m.ThreadStart = func(*Module, int32, int32) { t.Error("failed child ran") }
	InstallThreadLifetime(m, func(*Module, int32) { t.Error("failed child reclaimed") })
	m.Threads.nextTID.Store((1 << 29) - 1)
	if ThreadSpawn(m, 0) >= 0 || len(m.ThreadLifetime.maps) != 0 || m.Threads.WaitThreads() != nil {
		t.Fatal("failed spawn changed worker ownership")
	}
}

func TestCallerOwnedStackHasNoTrackedFree(t *testing.T) {
	m := lifetimeModule()
	lifetimeArgs(m, 256, 512, 0)
	m.ThreadStart = func(*Module, int32, int32) {}
	InstallThreadLifetime(m, func(*Module, int32) { t.Error("caller-owned allocation freed") })
	ThreadSpawn(m, 256)
	if m.Threads.WaitThreads() != nil || len(m.ThreadLifetime.maps) != 0 || DeferThreadAllocationFree(m, 0) {
		t.Fatal("caller-owned stack changed ownership")
	}
}

func TestReclaimerAddressReuseDoesNotEraseNewGeneration(t *testing.T) {
	m := lifetimeModule()
	lifetimeArgs(m, 256, 512, 4096)
	m.ThreadStart = func(*Module, int32, int32) {}
	var next *threadAllocation
	var nextOwner Module
	var calls int
	InstallThreadLifetime(m, func(*Module, int32) {
		calls++
		if calls == 1 {
			// The allocator may publish a reusable address before dlfree returns.
			nextOwner = *m
			next = m.ThreadLifetime.register(&nextOwner, 256)
		}
	})
	oldOwner := *m
	old := m.ThreadLifetime.register(&oldOwner, 256)
	m.ThreadLifetime.complete(&oldOwner, old)
	if !DeferThreadAllocationFree(m, 4096) || m.ThreadLifetime.maps[4096] != next {
		t.Fatal("previous reclaim erased a reused allocation generation")
	}
	m.ThreadLifetime.complete(&nextOwner, next)
	if !DeferThreadAllocationFree(m, 4096) || calls != 2 || len(m.ThreadLifetime.maps) != 0 {
		t.Fatal("new allocation generation was not reclaimed exactly once")
	}
}

func TestWorkerAllocationBindingRejectsInvalidInputs(t *testing.T) {
	for _, kind := range []string{"arg-oob", "td-oob", "empty", "map-oob", "duplicate"} {
		t.Run(kind, func(t *testing.T) {
			m := lifetimeModule()
			lifetimeArgs(m, 256, 512, 4096)
			m.ThreadStart = func(*Module, int32, int32) {}
			InstallThreadLifetime(m, func(*Module, int32) { t.Error("invalid input reclaimed") })
			arg := int32(256)
			switch kind {
			case "arg-oob":
				arg = -1
			case "td-oob":
				binary.LittleEndian.PutUint32(m.Memory[272:], 65536)
			case "empty":
				binary.LittleEndian.PutUint32(m.Memory[556:], 0)
			case "map-oob":
				binary.LittleEndian.PutUint32(m.Memory[552:], 65000)
			case "duplicate":
				owner := *m
				m.ThreadLifetime.register(&owner, arg)
			}
			defer func() {
				if recover() == nil {
					t.Error("invalid binding was accepted")
				}
			}()
			m.ThreadLifetime.register(m, arg)
		})
	}
}

func TestDeferredAllocatorFailureIsRetained(t *testing.T) {
	m := lifetimeModule()
	lifetimeArgs(m, 256, 512, 4096)
	m.ThreadStart = func(child *Module, _, _ int32) {
		DeferThreadAllocationFree(child, 4096)
		runtime.Goexit()
	}
	InstallThreadLifetime(m, func(*Module, int32) { panic("allocator-failure") })
	ThreadSpawn(m, 256)
	if m.Threads.WaitThreads() != "allocator-failure" || m.Threads.WaitThreads() != "allocator-failure" {
		t.Fatal("deferred allocator failure was lost")
	}
}

type lifetimePoisonYield struct {
	Wasi_snapshot_preview1Imports
	calls atomic.Int32
}

func (p *lifetimePoisonYield) Sched_yield(m *Module) int32 {
	p.calls.Add(1)
	m.Memory[9] = 99
	return 21
}

func TestLateReclaimerYieldCannotWriteDeadTLS(t *testing.T) {
	m := lifetimeModule()
	lifetimeArgs(m, 256, 512, 4096)
	poison := &lifetimePoisonYield{}
	m.Wasi_snapshot_preview1 = poison
	m.ThreadStart = func(child *Module, _, _ int32) {
		DeferThreadAllocationFree(child, 4096)
	}
	InstallThreadLifetime(m, func(raw *Module, _ int32) {
		if raw.Wasi_snapshot_preview1.Sched_yield(raw) != 0 {
			t.Error("late reclaimer could enter guest errno/TLS path")
		}
	})
	ThreadSpawn(m, 256)
	if m.Threads.WaitThreads() != nil || poison.calls.Load() != 0 || m.Memory[9] != 0 {
		t.Fatal("late yield accessed dead guest storage")
	}
}
