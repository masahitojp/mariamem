//go:build integration

package godefault

import (
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"math/big"
	"math/rand"
	"sync"
	"sync/atomic"
	"testing"
)

func TestMemoryEAOracle(t *testing.T) {
	m := &base.Module{MemSize: new(atomic.Uint64)}
	r := rand.New(rand.NewSource(190))
	xs := []uint64{0, 1, 2, 4, 8, 65535, 65536, 0xffffffff, 0x100000000, 1 << 63, ^uint64(0)}
	cases := 0
	check := func(bound, a, o, s uint64) {
		t.Helper()
		m.MemSize.Store(bound)
		sum := new(big.Int).SetUint64(a)
		sum.Add(sum, new(big.Int).SetUint64(o))
		sum.Add(sum, new(big.Int).SetUint64(s))
		want := sum.Cmp(new(big.Int).SetUint64(bound)) <= 0
		var got uint64
		var trap any
		func() { defer func() { trap = recover() }(); got = base.MemoryEA(m, a, o, s) }()
		if want {
			if trap != nil || got != a+o {
				t.Fatalf("valid %x %x %x %x got %x trap%v", bound, a, o, s, got, trap)
			}
		} else if fmt.Sprint(trap) != "wasm: memory access out of bounds" {
			t.Fatalf("invalid trap %v", trap)
		}
		cases++
	}
	for _, b := range xs {
		for _, a := range xs {
			for _, o := range xs {
				for _, s := range xs {
					check(b, a, o, s)
				}
			}
		}
	}
	for i := 0; i < 10000; i++ {
		check(r.Uint64(), r.Uint64(), r.Uint64(), r.Uint64())
	}
	m.MemSize.Store(8)
	if base.MemoryEA(m, 8, 0, 0) != 8 {
		t.Fatal("zero end")
	}
	m.MemSize.Store(16)
	if base.MemoryEA(m, 8, 0, 8) != 8 {
		t.Fatal("grow bound")
	}
	t.Log("oracle cases", cases)
}

func TestMemoryEASharedBound(t *testing.T) {
	m := &base.Module{MemSize: new(atomic.Uint64)}
	m.MemSize.Store(8)
	var w sync.WaitGroup
	w.Add(2)
	go func() {
		defer w.Done()
		for i := 0; i < 10000; i++ {
			m.MemSize.Store(8 + uint64(i%2)*8)
		}
	}()
	go func() {
		defer w.Done()
		for i := 0; i < 10000; i++ {
			if base.MemoryEA(m, 0, 0, 8) != 0 {
				t.Error("address")
			}
		}
	}()
	w.Wait()
}
