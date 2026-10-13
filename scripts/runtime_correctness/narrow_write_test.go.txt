//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"bytes"
	"sync"
	"sync/atomic"
	"testing"
	"unsafe"
)

func narrowWriterStore(m *Module, bits int, addr, v int32) {
	if bits == 8 {
		AtomicStore32_8(m, addr, 0, v)
	} else {
		AtomicStore32_16(m, addr, 0, v)
	}
}
func narrowWriterRead(m *Module, bits int, addr int32) uint32 {
	if bits == 8 {
		return uint32(AtomicLoad32_8u(m, addr, 0))
	}
	return uint32(AtomicLoad32_16u(m, addr, 0))
}
func narrowWriterCmp(m *Module, bits int, addr int32, expected, replacement uint32) uint32 {
	p := unsafe.Add(m.M, uintptr(AtomicEA(m, addr, 0, uint64(bits/8))))
	if bits == 8 {
		return atomicCmp8At(p, expected, replacement)
	}
	return atomicCmp16At(p, expected, replacement)
}
func TestNarrowWriterValuesAndBounds(t *testing.T) {
	for _, mapped := range []bool{false, true} {
		m := narrowTestModule(t, mapped)
		for _, contended := range []bool{false, true} {
			if contended {
				ForceContendedAtomics(m)
			}
			for _, bits := range []int{8, 16} {
				mask := uint32(1)<<bits - 1
				for lane := int32(0); lane < 4; lane += int32(bits / 8) {
					addr := 64 + lane
					for _, v := range []uint32{0, 1, 0x80, 0x91ff, 0xffffffff} {
						copy(m.Memory[60:72], bytes.Repeat([]byte{0x57}, 12))
						narrowWriterStore(m, bits, addr, int32(v))
						if got := narrowWriterRead(m, bits, addr); got != v&mask {
							t.Fatal(bits, got, v)
						}
						for i := int32(60); i < 72; i++ {
							if (i < addr || i >= addr+int32(bits/8)) && m.Memory[i] != 0x57 {
								t.Fatal("neighbor write", i)
							}
						}
						if old := narrowWriterCmp(m, bits, addr, v, 0xfedc); old != v&mask || narrowWriterRead(m, bits, addr) != 0xfedc&mask {
							t.Fatal("cmp truncation/old value")
						}
						if old := narrowWriterCmp(m, bits, addr, 0, 0x80); old != 0xfedc&mask || narrowWriterRead(m, bits, addr) != old {
							t.Fatal("cmp mismatch")
						}
						for _, op := range []string{"add", "sub", "and", "or", "xor", "xchg"} {
							narrowWriterStore(m, bits, addr, int32(v))
							ea := AtomicEA(m, addr, 0, uint64(bits/8))
							operand := uint32(0xa51f)
							old := AtomicSubword32(m, ea, uint(bits), func(o uint32) uint32 {
								switch op {
								case "add":
									return o + operand
								case "sub":
									return o - operand
								case "and":
									return o & operand
								case "or":
									return o | operand
								case "xor":
									return o ^ operand
								default:
									return operand
								}
							})
							want := operand
							switch op {
							case "add":
								want = (v & mask) + operand
							case "sub":
								want = (v & mask) - operand
							case "and":
								want = v & operand
							case "or":
								want = v | operand
							case "xor":
								want = v ^ operand
							}
							if old != v&mask || narrowWriterRead(m, bits, addr) != want&mask {
								t.Fatal("RMW", bits, op)
							}
						}
					}
				}
				last := int32(65536 - bits/8)
				narrowWriterStore(m, bits, last, 0x81fe)
				if narrowWriterRead(m, bits, last) != 0x81fe&mask {
					t.Fatal("last valid write")
				}
				before := append([]byte(nil), m.Memory[64:68]...)
				for _, f := range []func(){func() { narrowWriterStore(m, bits, 65536, 1) }, func() { narrowWriterStore(m, bits, -1, 1) }, func() {
					if bits == 8 {
						AtomicStore32_8(m, -1, 1, 1)
					} else {
						AtomicStore32_16(m, -1, 1, 1)
					}
				}} {
					narrowMustTrap(t, f)
				}
				if bits == 16 {
					narrowMustTrap(t, func() { narrowWriterStore(m, bits, 65, 1) })
				}
				if !bytes.Equal(before, m.Memory[64:68]) {
					t.Fatal("trap mutated memory")
				}
			}
		}
	}
}

func TestNarrowWriterOrdinaryNeighbor(t *testing.T) {
	for _, mapped := range []bool{false, true} {
		for _, bits := range []int{8, 16} {
			for _, op := range []string{"store", "rmw", "cmp"} {
				m := narrowTestModule(t, mapped)
				ForceContendedAtomics(m)
				var wg sync.WaitGroup
				wg.Add(2)
				gate := make(chan struct{})
				go func() {
					defer wg.Done()
					<-gate
					for i := 0; i < 10000; i++ {
						switch op {
						case "store":
							narrowWriterStore(m, bits, 66, int32(i))
						case "rmw":
							AtomicSubword32(m, 66, uint(bits), func(o uint32) uint32 { return o + 1 })
						case "cmp":
							narrowWriterCmp(m, bits, 66, uint32(i)&(uint32(1)<<bits-1), uint32(i+1))
						}
					}
				}()
				go func() {
					defer wg.Done()
					<-gate
					for i := 0; i < 10000; i++ {
						m.Memory[65] = byte(i)
					}
				}()
				close(gate)
				wg.Wait()
				want := uint32(10000)
				if op == "store" {
					want--
				}
				if narrowWriterRead(m, bits, 66) != want&(uint32(1)<<bits-1) || m.Memory[65] != byte(9999&255) {
					t.Fatal("disjoint neighbor contract")
				}
			}
		}
	}
}
func TestNarrowWriterSameTarget(t *testing.T) {
	for _, mapped := range []bool{false, true} {
		for _, bits := range []int{8, 16} {
			m := narrowTestModule(t, mapped)
			ForceContendedAtomics(m)
			var wg sync.WaitGroup
			wg.Add(4)
			for k := 0; k < 4; k++ {
				go func() {
					defer wg.Done()
					for i := 0; i < 10000; i++ {
						AtomicSubword32(m, 66, uint(bits), func(o uint32) uint32 { return o + 1 })
					}
				}()
			}
			wg.Wait()
			if narrowWriterRead(m, bits, 66) != 40000&(uint32(1)<<bits-1) {
				t.Fatal("lost increment")
			}
		}
	}
}
func TestNarrowWriterMixedWidthSC(t *testing.T) {
	for _, mapped := range []bool{false, true} {
		for _, bits := range []int{8, 16} {
			m := narrowTestModule(t, mapped)
			ForceContendedAtomics(m)
			wide := (*uint32)(unsafe.Add(m.M, 128))
			for trial := 0; trial < 1000; trial++ {
				narrowWriterStore(m, bits, 64, 0)
				atomic.StoreUint32(wide, 0)
				var a, b uint32
				var wg sync.WaitGroup
				wg.Add(2)
				gate := make(chan struct{})
				go func() {
					defer wg.Done()
					<-gate
					AtomicSubword32(m, 64, uint(bits), func(uint32) uint32 { return 1 })
					a = atomic.LoadUint32(wide)
				}()
				go func() { defer wg.Done(); <-gate; atomic.StoreUint32(wide, 1); b = narrowWriterRead(m, bits, 64) }()
				close(gate)
				wg.Wait()
				if a == 0 && b == 0 {
					t.Fatal("SC forbidden mixed-width result")
				}
			}
		}
	}
}
