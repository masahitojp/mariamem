// Copy only into the isolated generated/base module. This is an ordering
// reduction of buf_flush_page_cleaner, not a replacement pthread implementation.
package base

import (
	"sync"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"
)

func testModule() *Module {
	mem := make([]byte, 65536)
	size := &atomic.Uint64{}
	size.Store(65536)
	m := &Module{Memory: mem, M: unsafe.Pointer(&mem[0]), MemSize: size, MemShared: true, Threads: &ThreadPool{}}
	ForceContendedAtomics(m)
	return m
}
func parked(m *Module, ea uint64) int {
	m.Threads.parkMu.Lock()
	defer m.Threads.parkMu.Unlock()
	return len(m.Threads.parked[ea])
}
func awaitPark(t *testing.T, m *Module, ea uint64) {
	t.Helper()
	limit := time.Now().Add(time.Second)
	for parked(m, ea) == 0 {
		if time.Now().After(limit) {
			t.Fatal("not parked")
		}
		time.Sleep(time.Microsecond * 50)
	}
}
func TestWaitContract(t *testing.T) {
	m := testModule()
	p := AtomicPtr32At(m, 64)
	atomic.StoreUint32(p, 2)
	if AtomicNotify(m, 64, 0, 1) != 0 {
		t.Fatal("notify must not retain a permit")
	}
	if AtomicWait32At(m, 64, 1, -1) != 1 {
		t.Fatal("expected mismatch must return immediately")
	}
	// A notifier races the compare/registration boundary. AtomicWait holds the
	// same parking lock across both, so the waiter must never lose this wake.
	for i := 0; i < 100; i++ {
		atomic.StoreUint32(p, 2)
		compared := make(chan struct{})
		notifying := make(chan struct{})
		done := make(chan int32, 1)
		go func() { <-compared; close(notifying); atomic.StoreUint32(p, 0); AtomicNotify(m, 64, 0, 1) }()
		started := time.Now()
		go func() {
			done <- AtomicWait(m, 64, int64(time.Second), func() bool { close(compared); <-notifying; return true })
		}()
		if rc := <-done; rc != 0 {
			t.Fatalf("registration wake lost: %d", rc)
		}
		if time.Since(started) > time.Millisecond*500 {
			t.Fatal("unexpected timeout fallback")
		}
	}
	atomic.StoreUint32(p, 2)
	done := make(chan int32, 2)
	for i := 0; i < 2; i++ {
		go func() { done <- AtomicWait32At(m, 64, 2, int64(time.Second)) }()
	}
	limit := time.Now().Add(time.Second)
	for parked(m, 64) != 2 {
		if time.Now().After(limit) {
			t.Fatal("two waiters absent")
		}
		time.Sleep(time.Microsecond * 50)
	}
	if AtomicNotify(m, 64, 0, 0) != 0 || parked(m, 64) != 2 {
		t.Fatal("zero-count wake changed queue")
	}
	if AtomicNotify(m, 64, 0, 1) != 1 {
		t.Fatal("one-count wake failed")
	}
	if <-done != 0 || parked(m, 64) != 1 {
		t.Fatal("wrong wake count")
	}
	if AtomicNotify(m, 64, 0, 1) != 1 || <-done != 0 {
		t.Fatal("remaining waiter failed")
	}
}

// Like musl's private condition variable: no waiter means no stored signal;
// a registered waiter has its own barrier word, changed before futex wake.
type reducedCond struct {
	mu         sync.Mutex
	registered bool
	m          *Module
	ea         uint64
}

func (c *reducedCond) signal() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.registered {
		return false
	}
	c.registered = false
	atomic.StoreUint32(AtomicPtr32At(c.m, c.ea), 0)
	AtomicNotify(c.m, int32(c.ea), 0, 1)
	return true
}
func (c *reducedCond) wait(mutex *sync.Mutex) int32 {
	c.mu.Lock()
	atomic.StoreUint32(AtomicPtr32At(c.m, c.ea), 2)
	c.registered = true
	c.mu.Unlock()
	mutex.Unlock()
	rc := AtomicWait32At(c.m, c.ea, 2, int64(time.Second))
	mutex.Lock()
	c.mu.Lock()
	c.registered = false
	c.mu.Unlock()
	return rc
}
func TestPageCleanerOrdering(t *testing.T) {
	for _, early := range []bool{true, false} {
		label := "registered-before-signal"
		if early {
			label = "signal-before-registration"
		}
		t.Run(label, func(t *testing.T) {
			m := testModule()
			c := &reducedCond{m: m, ea: 128}
			var mutex sync.Mutex
			var target atomic.Int64
			read := make(chan struct{})
			done := make(chan int32, 1)
			if early {
				mutex.Lock()
			}
			go func() {
				snapshot := target.Load()
				close(read)
				mutex.Lock()
				// buf0flu.cc reads the target BEFORE this lock, then decides to wait
				// using idle/dirty state, without rechecking the target under the lock.
				var rc int32
				if snapshot == 0 {
					rc = c.wait(&mutex)
				}
				if target.Load() != 12288 {
					panic("flush request not visible")
				}
				mutex.Unlock()
				done <- rc
			}()
			<-read
			if !early {
				awaitPark(t, m, 128)
				mutex.Lock()
			}
			target.Store(12288)
			notified := c.signal()
			started := time.Now()
			mutex.Unlock()
			rc := <-done
			elapsed := time.Since(started)
			if early {
				if notified || rc != 2 || elapsed < time.Millisecond*900 {
					t.Fatalf("expected legitimate 1s timer: signal=%v rc=%d elapsed=%v", notified, rc, elapsed)
				}
			} else if !notified || rc != 0 || elapsed > time.Millisecond*500 {
				t.Fatalf("registered wake failed: %v %d %v", notified, rc, elapsed)
			}
			t.Logf("signal_delivered=%v wait_result=%d elapsed=%v", notified, rc, elapsed)
		})
	}
}
