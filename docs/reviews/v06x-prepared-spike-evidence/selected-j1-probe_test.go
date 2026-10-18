package probe

import (
	_ "embed"
	"encoding/binary"
	base "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"
)

//go:embed data.bin
var data []byte

func waitEvent(t *testing.T, ch <-chan struct{}) {
	t.Helper()
	select {
	case <-ch:
	case <-time.After(2 * time.Second):
		t.Fatal("guest event did not complete")
	}
}

func TestJoinAllocationLastAccess(t *testing.T) {
	protected := os.Getenv("JOIN_PROTECTED") == "1"
	for _, tc := range []struct {
		name               string
		waiters            int32
		deferReclaim, self bool
	}{
		{"early-free", 1, false, false}, {"completed-before-free", 1, true, false},
		{"no-post-unlock-wake", 0, false, false}, {"detached-self-free", 1, false, true},
	} {
		if tc.self && !protected {
			continue
		}
		t.Run(tc.name, func(t *testing.T) {
			const initial = 256 << 20
			const maximum = 512 << 20
			var memory []byte
			var mapping *base.MemoryMapping
			if os.Getenv("JOIN_BACKING") == "mmap" {
				var err error
				mapping, err = base.NewMemoryMapping(initial, maximum)
				if err != nil {
					t.Fatal(err)
				}
				memory = mapping.Bytes()
				defer mapping.Close()
			} else {
				memory = make([]byte, maximum)
			}
			size := &atomic.Uint64{}
			size.Store(initial)
			h := &host{WasiStubs: base.DefaultWASI()}
			m := &base.Module{Memory: memory, M: unsafe.Pointer(&memory[0]), MaxMem: maximum, MemSize: size, MemMu: &sync.Mutex{}, MemShared: true, Threads: &base.ThreadPool{}, Wasix_32v1: h, Wasi_snapshot_preview1: h, G0: 8388608, G1: 32768}
			if mapping != nil {
				m.PrepareMemoryGrow = mapping.Grow
			}
			base.ForceContendedAtomics(m)
			copy(memory[8388608:], data[:6208038])
			copy(memory[14596672:], data[6208038:6850658])
			copy(memory[15239296:], data[6850658:])
			put := func(addr int32, v int32) { binary.LittleEndian.PutUint32(memory[uint32(addr):], uint32(v)) }
			put(32772, 33024)
			put(33024+48, 0x3fffffff)
			ptr := Fn152(m, 262144)
			if ptr <= 0 {
				t.Fatal("malloc failed")
			}
			td := ptr + 262144 - 1024
			arg := ptr + 262144 - 4096
			marker := arg - 1
			put(td+28, 0)
			put(td+40, ptr)
			put(td+44, 262144)
			put(arg+16, td)
			put(15289660, 123)
			put(15290768, 0)
			put(15290772, tc.waiters)
			waking := make(chan struct{}, 1)
			resume := make(chan struct{})
			var release sync.Once
			t.Cleanup(func() { release.Do(func() { close(resume) }) })
			h.hook = func(child *base.Module, out int32) {
				if child == m || out != marker {
					t.Errorf("wrong result alias: %d/%d", out, marker)
				}
				waking <- struct{}{}
				<-resume
			}
			var rawFrees atomic.Int32
			m.ThreadStart = func(child *base.Module, tid, args int32) {
				child.G0 = arg
				if tc.self {
					Fn153(child, ptr)
				}
				Fn217(child)
				runtime.Goexit()
			}
			if protected {
				base.InstallThreadLifetime(m, func(raw *base.Module, p int32) { rawFrees.Add(1); Fn153(raw, p) })
			}
			if base.ThreadSpawn(m, arg) <= 0 {
				t.Fatal("spawn failed")
			}
			joinDone := make(chan struct{})
			if tc.waiters != 0 {
				waitEvent(t, waking)
			}
			join := func() {
				if rc := Fn221(m, td); rc != 0 {
					t.Errorf("join=%d", rc)
				}
				close(joinDone)
			}
			if tc.self {
				if rawFrees.Load() != 0 {
					t.Fatal("self allocation freed before final wake result store")
				}
				release.Do(func() { close(resume) })
				if trap := m.Threads.WaitThreads(); trap != nil {
					t.Fatalf("worker trap: %v", trap)
				}
			} else if tc.deferReclaim || tc.waiters == 0 {
				release.Do(func() { close(resume) })
				if trap := m.Threads.WaitThreads(); trap != nil {
					t.Fatalf("worker trap: %v", trap)
				}
				join()
			} else {
				go join()
				if protected {
					// Observe the actual allocator handoff waiting before any allocator lock.
					// Stack observation is disposable instrumentation, not a runtime dependency.
					deadline := time.Now().Add(2 * time.Second)
					for {
						buf := make([]byte, 1<<20)
						n := runtime.Stack(buf, true)
						if strings.Contains(string(buf[:n]), "base.DeferThreadAllocationFree") {
							break
						}
						select {
						case <-joinDone:
							t.Fatal("join/free completed while worker was paused")
						default:
						}
						if time.Now().After(deadline) {
							t.Fatal("allocator handoff wait not observed")
						}
						runtime.Gosched()
					}
					if rawFrees.Load() != 0 {
						t.Fatal("allocator ran before worker completion")
					}
					release.Do(func() { close(resume) })
					waitEvent(t, joinDone)
				} else {
					waitEvent(t, joinDone)
				}
			}
			reused := Fn152(m, 262144)
			if reused != ptr {
				t.Fatalf("allocation not reused: %d/%d", ptr, reused)
			}
			memory[marker] = 165
			release.Do(func() { close(resume) })
			if trap := m.Threads.WaitThreads(); trap != nil {
				t.Fatalf("worker trap: %v", trap)
			}
			observed := memory[marker]
			t.Logf("backing=%s protected=%v case=%s map=%d reused=%d result=%d canary=%d raw_frees=%d", os.Getenv("JOIN_BACKING"), protected, tc.name, ptr, reused, marker, observed, rawFrees.Load())
			if protected && rawFrees.Load() != 1 {
				t.Errorf("raw allocator executions=%d", rawFrees.Load())
			}
			if observed != 165 {
				t.Fatalf("lifetime violation: replacement byte changed from 165 to %d after join/free/reuse", observed)
			}
			runtime.KeepAlive(m)
		})
		runtime.GC()
	}
}
