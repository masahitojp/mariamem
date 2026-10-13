// Handwritten completion/reclamation owner for the pinned WASIX thread ABI.
package base

import (
	"encoding/binary"
	"runtime"
	"sync"
)

// ThreadLifetime belongs to one DB. Only exact malloc-owned worker map bases
// are registered; other frees retain the original allocator behavior.
type ThreadLifetime struct {
	mu      sync.RWMutex
	maps    map[uint32]*threadAllocation
	reclaim func(*Module, int32)
}

type threadAllocation struct {
	ptr      uint32
	owner    *Module
	done     chan struct{}
	deferred bool // protected by ThreadLifetime.mu
}

// The accepted dlfree closure can only call sched_yield. Its generated errno
// branch would write TLS on error, so late reclamation uses the same infallible
// Go scheduler operation as production WASI, with no linear-memory accesses.
// All other imports are preserved; their use would require a new closure review.
type threadReclaimYield struct{ Wasi_snapshot_preview1Imports }

func (threadReclaimYield) Sched_yield(*Module) int32 {
	runtime.Gosched()
	return 0
}

func threadReclaimModule(m *Module) *Module {
	raw := new(Module)
	*raw = *m
	raw.ThreadLifetime = nil
	raw.Wasi_snapshot_preview1 = threadReclaimYield{m.Wasi_snapshot_preview1}
	return raw
}

// InstallThreadLifetime wraps the existing entry without changing the Wasm ABI.
// Install before execution; callers supply the checksum-bound stackless reclaimer.
func InstallThreadLifetime(m *Module, reclaim func(*Module, int32)) {
	if m.ThreadLifetime != nil || m.ThreadStart == nil || reclaim == nil {
		panic("mariamem: invalid thread lifetime installation")
	}
	pool := &ThreadLifetime{maps: make(map[uint32]*threadAllocation), reclaim: reclaim}
	start := m.ThreadStart
	m.ThreadLifetime = pool
	m.ThreadStart = func(child *Module, tid, arg int32) {
		a := pool.register(child, arg)
		if a != nil {
			defer pool.complete(child, a)
		}
		start(child, tid, arg)
	}
}

func threadWord(m *Module, addr uint64) uint32 {
	ea := MemoryEA(m, addr, 0, 4)
	return binary.LittleEndian.Uint32(m.Memory[ea : ea+4])
}

func (p *ThreadLifetime) register(m *Module, arg int32) *threadAllocation {
	// Accepted start_args.pthread_self_ptr = +16; pthread.map_base = +40,
	// map_size = +44. The generated entry/reclaimer identities are installer pins.
	td := uint64(threadWord(m, uint64(uint32(arg))+16))
	ptr := threadWord(m, td+40)
	if ptr == 0 {
		return nil // caller-provided stack/TLS: no malloc-owned map to reclaim
	}
	size := threadWord(m, td+44)
	if size == 0 {
		panic("mariamem: empty worker allocation")
	}
	MemoryEA(m, uint64(ptr), 0, uint64(size))
	a := &threadAllocation{ptr: ptr, owner: m, done: make(chan struct{})}
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.maps[ptr] != nil {
		panic("mariamem: overlapping worker allocation lifetime")
	}
	p.maps[ptr] = a
	return a
}

func (p *ThreadLifetime) complete(m *Module, a *threadAllocation) {
	// This defer runs after the guest body and all its defers, including Goexit
	// and panic unwinding. Close only after any deferred allocator work also ends.
	defer close(a.done)
	p.mu.Lock()
	deferred := a.deferred
	if deferred {
		if p.maps[a.ptr] != a {
			p.mu.Unlock()
			panic("mariamem: stale deferred worker allocation")
		}
		delete(p.maps, a.ptr)
	}
	p.mu.Unlock()
	if deferred {
		// No more worker execution follows. Fn153 has no guest stack accesses;
		// its sole call is the infallible memory-free scheduler operation above.
		p.reclaim(threadReclaimModule(m), int32(a.ptr))
	}
}

// DeferThreadAllocationFree runs before ANY allocator instruction/lock. True
// means self-reclaim is deferred, or a foreign reclaim has been performed here.
func DeferThreadAllocationFree(m *Module, ptr int32) bool {
	p := m.ThreadLifetime
	if p == nil {
		return false
	}
	key := uint32(ptr)
	p.mu.RLock()
	a := p.maps[key]
	p.mu.RUnlock()
	if a == nil {
		return false
	}
	if a.owner == m {
		// A detached worker must not wait for itself, nor free its own live stack.
		p.mu.Lock()
		defer p.mu.Unlock()
		if p.maps[key] != a || a.deferred {
			panic("mariamem: duplicate worker self-reclaim")
		}
		a.deferred = true
		return true
	}
	<-a.done // no registry or guest allocator lock is held while waiting
	p.mu.Lock()
	if p.maps[key] != a {
		p.mu.Unlock()
		panic("mariamem: duplicate or stale worker reclaim")
	}
	delete(p.maps, key) // permit a newly allocated generation to register this address
	p.mu.Unlock()
	p.reclaim(threadReclaimModule(m), ptr)
	return true
}
