//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"errors"
	"syscall"
	"testing"
)

func TestBatchLogicalAndRW(t *testing.T) {
	before := MemoryMappingStats()
	b, e := NewMemoryMapping(65536, 32<<20)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	b.memory[0] = 77
	ptr := &b.memory[0]
	if e = b.Grow(65536, 2*65536); e != nil {
		t.Fatal(e)
	}
	if b.enabled != 2*65536 || b.rw != 16<<20 {
		t.Fatal(b.enabled, b.rw)
	}
	calls := MemoryMappingStats()["protect_calls"]
	if e = b.Grow(2*65536, 3*65536); e != nil {
		t.Fatal(e)
	}
	if MemoryMappingStats()["protect_calls"] != calls || b.memory[2*65536] != 0 || b.memory[0] != 77 || &b.memory[0] != ptr {
		t.Fatal("data/zero/pointer/no extra protect")
	}
	if e = b.Grow(16<<20, 17<<20); !errors.Is(e, syscall.EINVAL) {
		t.Fatal("RW extent accepted as logical old")
	}
	if e = b.Grow(3*65536, 32<<20); e != nil {
		t.Fatal(e)
	}
	if e = b.Grow(32<<20, (32<<20)+65536); !errors.Is(e, syscall.EINVAL) {
		t.Fatal("maximum")
	}
	if e = b.Close(); e != nil {
		t.Fatal(e)
	}
	if MemoryMappingStats()["active_rw_bytes"] != before["active_rw_bytes"] {
		t.Fatal("RW accounting")
	}
}
func TestBatchFailureRecovery(t *testing.T) {
	for _, mode := range []string{"fallback", "both_fail", "rollback_fail"} {
		t.Run(mode, func(t *testing.T) {
			before := MemoryMappingStats()
			b, e := NewMemoryMapping(65536, 32<<20)
			if e != nil {
				t.Fatal(e)
			}
			defer b.Close()
			b.memory[0] = 91
			real := b.protect
			calls := 0
			b.protect = func(p []byte, prot int) error {
				calls++
				if prot == syscall.PROT_NONE {
					if mode == "rollback_fail" {
						return syscall.EBUSY
					}
					return real(p, prot)
				}
				if calls == 1 || mode == "both_fail" {
					if e := real(p[:65536], prot); e != nil {
						return e
					}
					return syscall.ENOMEM
				}
				return real(p, prot)
			}
			e = b.Grow(65536, 2*65536)
			if mode == "fallback" {
				if e != nil || b.enabled != 2*65536 || b.rw != 2*65536 || calls != 3 {
					t.Fatal(e, b.enabled, b.rw, calls)
				}
			} else {
				if !errors.Is(e, syscall.ENOMEM) || b.enabled != 65536 {
					t.Fatal("failure published logical size", e, b.enabled)
				}
				if mode == "both_fail" {
					if b.rw != 65536 || b.poisoned || calls != 4 {
						t.Fatal("rollback state")
					}
					b.protect = real
					if e = b.Grow(65536, 2*65536); e != nil {
						t.Fatal("retry", e)
					}
				} else {
					if !b.poisoned || !errors.Is(e, syscall.EBUSY) {
						t.Fatal("lost rollback failure", e)
					}
					b.protect = real
					if e = b.Grow(65536, 2*65536); !errors.Is(e, syscall.EINVAL) {
						t.Fatal("poisoned growth")
					}
				}
			}
			if b.memory[0] != 91 {
				t.Fatal("old data damaged")
			}
			unmap := b.unmap
			b.unmap = func([]byte) error { return syscall.EBUSY }
			if e = b.Close(); !errors.Is(e, syscall.EBUSY) {
				t.Fatal(e)
			}
			b.unmap = unmap
			if e = b.Close(); e != nil {
				t.Fatal(e)
			}
			if e = b.Close(); e != nil {
				t.Fatal(e)
			}
			after := MemoryMappingStats()
			if after["active_mappings"] != before["active_mappings"] || after["active_rw_bytes"] != before["active_rw_bytes"] {
				t.Fatal("ownership/counters")
			}
		})
	}
}
