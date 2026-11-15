//go:build mappingspike && darwin && arm64

package base

import (
	"errors"
	"os"
	"runtime"
	"sync"
	"syscall"
	"testing"
	"unsafe"
)

// Isolated test owner. No production release closure is changed.
type resetSlot struct {
	mu         sync.Mutex
	b          *MemoryMapping
	epoch      uint64
	busy, debt bool
	reset      func([]byte) error
}

func replaceAnonymous(mem []byte) error {
	p := uintptr(unsafe.Pointer(&mem[0]))
	got, _, e := syscall.Syscall6(syscall.SYS_MMAP, p, uintptr(len(mem)), syscall.PROT_NONE, syscall.MAP_FIXED|syscall.MAP_PRIVATE|syscall.MAP_ANON, ^uintptr(0), 0)
	runtime.KeepAlive(mem)
	if e != 0 {
		return e
	}
	if got != p {
		panic("MAP_FIXED address mismatch")
	}
	return nil
}
func (s *resetSlot) acquire(initial uint64, fd int, ranges []ImageRange) (uint64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.busy || s.debt || s.b == nil {
		return 0, syscall.EBUSY
	}
	if e := s.b.Grow(0, initial); e != nil {
		s.debt = true
		return 0, e
	}
	for _, r := range ranges {
		if e := replaceImagePages(uintptr(unsafe.Pointer(&s.b.memory[r.Offset])), uintptr(r.Length), fd, r.Offset); e != nil {
			s.debt = true
			return 0, e
		}
	}
	s.epoch++
	s.busy = true
	return s.epoch, nil
}
func (s *resetSlot) release(epoch uint64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.busy || s.debt || s.epoch != epoch {
		return syscall.EINVAL
	}
	if e := s.reset(s.b.memory); e != nil {
		s.debt = true
		return e
	}
	// The exact original syscall.Mmap slice and tracking entry remain owned.
	mappingEnabled.Add(^(s.b.enabled - 1))
	s.b.enabled = 0
	s.busy = false
	return nil
}
func (s *resetSlot) close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.b == nil {
		return nil
	}
	if e := s.b.Close(); e != nil {
		s.debt = true
		return e
	}
	s.b = nil
	return nil
}

func TestResetSpikeSafety(t *testing.T) {
	before := MemoryMappingStats()
	const initial = 2 * 65536
	const maximum = 4 * 65536
	f, e := os.CreateTemp(t.TempDir(), "image")
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	if e = f.Truncate(maximum); e != nil {
		t.Fatal(e)
	}
	page := uint64(os.Getpagesize())
	ranges := []ImageRange{{page, page}}
	want := make([]byte, initial)
	for i := page; i < 2*page; i++ {
		want[i] = byte(i%251 + 1)
	}
	if _, e = f.WriteAt(want[page:2*page], int64(page)); e != nil {
		t.Fatal(e)
	}
	b, e := NewMemoryMapping(0, maximum)
	if e != nil {
		t.Fatal(e)
	}
	s := &resetSlot{b: b, reset: replaceAnonymous}
	defer s.close()
	for cycle := 0; cycle < 4; cycle++ {
		epoch, e := s.acquire(initial, int(f.Fd()), ranges)
		if e != nil {
			t.Fatal(e)
		}
		for i, v := range want {
			if b.memory[i] != v {
				t.Fatalf("cycle%d byte%d", cycle, i)
			}
		}
		if e = b.Grow(initial, maximum); e != nil {
			t.Fatal(e)
		}
		for i := initial; i < maximum; i++ {
			if b.memory[i] != 0 {
				t.Fatal("grown bytes retained")
			}
		}
		for i := range b.memory {
			b.memory[i] = byte(cycle + 11)
		}
		if e = s.release(epoch); e != nil {
			t.Fatal(e)
		}
		if !errors.Is(s.release(epoch), syscall.EINVAL) {
			t.Fatal("duplicate release accepted")
		}
		if cycle > 0 && !errors.Is(s.release(epoch-1), syscall.EINVAL) {
			t.Fatal("stale release accepted")
		}
	}
	epoch, e := s.acquire(initial, int(f.Fd()), ranges)
	if e != nil {
		t.Fatal(e)
	}
	// Failure occurs before syscall. Real partial MAP_FIXED failure remains a separate OS question.
	s.reset = func([]byte) error { return syscall.ENOMEM }
	if !errors.Is(s.release(epoch), syscall.ENOMEM) {
		t.Fatal("lost reset failure")
	}
	if _, e = s.acquire(initial, int(f.Fd()), ranges); e == nil {
		t.Fatal("debt reused")
	}
	realUnmap := b.unmap
	b.unmap = func([]byte) error { return syscall.EBUSY }
	if e = s.close(); e == nil {
		t.Fatal("lost release debt")
	}
	b.unmap = realUnmap
	if e = s.close(); e != nil {
		t.Fatal(e)
	}
	for _, k := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if MemoryMappingStats()[k] != before[k] {
			t.Fatal(k)
		}
	}
}

func TestResetSpikeFailures(t *testing.T) {
	for _, kind := range []string{"protect", "overlay", "after-reset"} {
		t.Run(kind, func(t *testing.T) {
			before := MemoryMappingStats()
			b, e := NewMemoryMapping(0, 4*65536)
			if e != nil {
				t.Fatal(e)
			}
			s := &resetSlot{b: b, reset: replaceAnonymous}
			defer s.close()
			if kind == "protect" {
				b.protect = func([]byte, int) error { return syscall.EACCES }
			}
			rs := []ImageRange(nil)
			if kind == "overlay" {
				rs = []ImageRange{{0, uint64(os.Getpagesize())}}
			}
			epoch, e := s.acquire(65536, -1, rs)
			if kind == "after-reset" {
				if e != nil {
					t.Fatal(e)
				}
				s.reset = func(m []byte) error {
					if e := replaceAnonymous(m); e != nil {
						return e
					}
					return syscall.EIO
				}
				e = s.release(epoch)
			}
			if e == nil || !s.debt {
				t.Fatal("failed operation admitted reuse")
			}
			if _, e = s.acquire(65536, -1, nil); e == nil {
				t.Fatal("debt admitted")
			}
			if e = s.close(); e != nil {
				t.Fatal(e)
			}
			for _, k := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
				if MemoryMappingStats()[k] != before[k] {
					t.Fatal(k)
				}
			}
		})
	}
}
func TestResetSpikeEpochConcurrency(t *testing.T) {
	b, e := NewMemoryMapping(0, 4*65536)
	if e != nil {
		t.Fatal(e)
	}
	s := &resetSlot{b: b, reset: replaceAnonymous}
	defer s.close()
	a, e := s.acquire(65536, -1, nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = s.release(a); e != nil {
		t.Fatal(e)
	}
	current, e := s.acquire(65536, -1, nil)
	if e != nil {
		t.Fatal(e)
	}
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if !errors.Is(s.release(a), syscall.EINVAL) {
				t.Error("stale owner released current")
			}
			if _, e := s.acquire(65536, -1, nil); !errors.Is(e, syscall.EBUSY) {
				t.Error("concurrent acquisition")
			}
		}()
	}
	wg.Wait()
	if e = s.release(current); e != nil {
		t.Fatal(e)
	}
}
