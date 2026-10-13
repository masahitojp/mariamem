package base

import (
	"fmt"
	"runtime"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"
)

func waitTimeoutModule() *Module {
	memory := make([]byte, 65536)
	size := &atomic.Uint64{}
	size.Store(uint64(len(memory)))
	m := &Module{Memory: memory, M: unsafe.Pointer(&memory[0]), MemSize: size, MemShared: true, Threads: &ThreadPool{}}
	ForceContendedAtomics(m)
	return m
}

func TestWaitTimeoutPositiveRange(t *testing.T) {
	checkWaitTimeoutPositiveRange(t, map[string]func(*Module, uint64, int64) int32{
		"wait32": func(m *Module, ea uint64, timeout int64) int32 { return AtomicWait32At(m, ea, 0, timeout) },
		// This guest emits no wait64 wrapper. Exercise its shared parking/timer
		// owner with a 64-bit comparison; the opcode fixture tests the wrapper.
		"common64": func(m *Module, ea uint64, timeout int64) int32 {
			return AtomicWait(m, ea, timeout, func() bool {
				return atomic.LoadUint64((*uint64)(unsafe.Add(m.M, ea))) == 0
			})
		},
	})
}

func checkWaitTimeoutPositiveRange(t *testing.T, widths map[string]func(*Module, uint64, int64) int32) {
	const boundary = int64(1<<63-1) - int64(time.Millisecond)
	for _, timeout := range []int64{boundary - 1, boundary, boundary + 1, 1<<63 - 1, -1} {
		for width, wait := range widths {
			t.Run(fmt.Sprintf("%d/%s", timeout, width), func(t *testing.T) {
				m := waitTimeoutModule()
				done := make(chan int32, 1)
				go func() {
					done <- wait(m, 64, timeout)
				}()
				deadline := time.Now().Add(time.Second)
				for {
					m.Threads.parkMu.Lock()
					parked := len(m.Threads.parked[64]) != 0
					m.Threads.parkMu.Unlock()
					if parked {
						break
					}
					select {
					case rc := <-done:
						t.Fatalf("positive or indefinite wait returned %d before notify", rc)
					default:
					}
					if time.Now().After(deadline) {
						t.Fatal("wait did not register")
					}
					runtime.Gosched()
				}
				// Cleanup remains necessary if a boundary failure is reproduced.
				t.Cleanup(func() { AtomicNotify(m, 64, 0, 1) })
				select {
				case rc := <-done:
					t.Fatalf("positive or indefinite wait returned %d before notify", rc)
				case <-time.After(10 * time.Millisecond):
				}
				AtomicNotify(m, 64, 0, 1)
				select {
				case rc := <-done:
					if rc != 0 {
						t.Fatalf("notified wait returned %d", rc)
					}
				case <-time.After(time.Second):
					t.Fatal("notification did not finish wait")
				}
			})
		}
	}
}

func TestWaitTimeoutZeroShortAndMismatch(t *testing.T) {
	for _, timeout := range []int64{0, 1, int64(time.Millisecond)} {
		m := waitTimeoutModule()
		if rc := AtomicWait32At(m, 64, 0, timeout); rc != 2 {
			t.Fatalf("timeout %d returned %d", timeout, rc)
		}
		m.Threads.parkMu.Lock()
		left := len(m.Threads.parked[64])
		m.Threads.parkMu.Unlock()
		if left != 0 {
			t.Fatal("expired wait remains registered")
		}
	}
	m := waitTimeoutModule()
	if rc := AtomicWait32At(m, 64, 1, 1<<63-1); rc != 1 {
		t.Fatalf("mismatch returned %d", rc)
	}
}
