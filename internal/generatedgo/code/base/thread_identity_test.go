package base

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
)

func TestThreadIdentityFailureBeforeLaunch(t *testing.T) {
	for _, previous := range []int32{(1 << 29) - 1, 1 << 29, 1<<31 - 1, -1} {
		t.Run(fmt.Sprint(previous), func(t *testing.T) {
			m := &Module{Threads: &ThreadPool{}}
			m.Threads.nextTID.Store(previous)
			var ran atomic.Bool
			m.ThreadStart = func(*Module, int32, int32) { ran.Store(true) }
			if tid := ThreadSpawn(m, 123); tid >= 0 {
				t.Fatalf("invalid counter %d spawned TID %d", previous, tid)
			}
			if p := m.Threads.WaitThreads(); p != nil {
				t.Fatal(p)
			}
			if ran.Load() {
				t.Fatal("failed spawn started child")
			}
			if got := m.Threads.nextTID.Load(); got != previous {
				t.Fatalf("failure changed counter: %d", got)
			}
		})
	}
}

func TestThreadIdentityConcurrentAllocationAndExhaustion(t *testing.T) {
	const attempts = 32
	for _, previous := range []int32{0, (1 << 29) - 11} {
		t.Run(fmt.Sprint(previous), func(t *testing.T) {
			m := &Module{Threads: &ThreadPool{}}
			m.Threads.nextTID.Store(previous)
			gate := make(chan struct{})
			returned := make(chan int32, attempts)
			ran := make(chan int32, attempts)
			var launches sync.WaitGroup
			for range attempts {
				launches.Add(1)
				go func() {
					defer launches.Done()
					returned <- ThreadLaunch(m, func(child *Module, tid int32) {
						if child == m || child.Threads != m.Threads || !AtomicsContended(child) {
							panic("child identity/publication incorrect")
						}
						ran <- tid
						<-gate
					})
				}()
			}
			launches.Wait()
			close(returned)
			close(gate)
			if p := m.Threads.WaitThreads(); p != nil {
				t.Fatal(p)
			}
			close(ran)
			ids := map[int32]bool{}
			success := 0
			for tid := range returned {
				if tid < 0 {
					continue
				}
				if tid == 0 || tid >= 1<<29 || ids[tid] {
					t.Fatalf("invalid/duplicate ID %d", tid)
				}
				ids[tid] = true
				success++
			}
			executed := 0
			for tid := range ran {
				if !ids[tid] {
					t.Fatalf("unreported child %d", tid)
				}
				executed++
			}
			expected := attempts
			if previous != 0 {
				expected = 10
			}
			if success != expected || executed != expected {
				t.Fatalf("successful=%d executed=%d want=%d", success, executed, expected)
			}
			if !AtomicsContended(m) {
				t.Fatal("contention marker reset after worker completion")
			}
			if m.Threads.nextTID.Load() != previous+int32(expected) {
				t.Fatal("allocator advanced on failed launch")
			}
		})
	}
}

func TestThreadIdentityMissingEntryDoesNotAllocate(t *testing.T) {
	m := &Module{Threads: &ThreadPool{}}
	if ThreadSpawn(m, 0) >= 0 {
		t.Fatal("missing entry accepted")
	}
	if m.Threads.nextTID.Load() != 0 {
		t.Fatal("missing entry allocated ID")
	}
}
