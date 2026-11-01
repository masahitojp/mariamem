//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"testing"
)

func TestBatchAheadRemainsLogicallyOutOfBounds(t *testing.T) {
	m, release, e := newMemoryModule(mappedTestHost())
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	if base.MemoryGrow(m, 1) != 4096 || base.MemorySize(m) != 4097 {
		t.Fatal("logical growth")
	}
	addr := uint64(4097 * 65536)
	if base.MemoryInBounds(m, addr, 0, 1) {
		t.Fatal("ahead RW considered in bounds")
	}
	for name, f := range map[string]func(){"scalar": func() { base.MemoryEA(m, addr, 0, 1) }, "atomic": func() { base.AtomicEA(m, int32(addr), 0, 4) }} {
		t.Run(name, func(t *testing.T) {
			defer func() {
				if recover() == nil {
					t.Error("ahead RW did not trap")
				}
			}()
			f()
		})
	}
	if base.MemoryGrow(m, 1) != 4097 || m.Memory[addr] != 0 {
		t.Fatal("newly exposed page not zero")
	}
}
