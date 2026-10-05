package base

import (
	"encoding/binary"
	"sync"
	"sync/atomic"
	"testing"
	"unsafe"
)

// The backing is larger than logical memory, exactly as released shared memory
// and reserved mmap are. Invalid imports must reject before touching the tail.
func TestHostImportLogicalMemory(t *testing.T) {
	mem := make([]byte, 2*65536)
	size := new(atomic.Uint64)
	size.Store(65536)
	m := &Module{Memory: mem, M: unsafe.Pointer(&mem[0]), MemSize: size, MemShared: true, MemMu: new(sync.Mutex), MaxMem: 2 * 65536}
	w := DefaultWASI()
	for _, c := range []struct{ off, n int32 }{{65536, 1}, {65535, 2}, {-1, 1}, {1, -1}, {2147483647, 8}} {
		if w.memSlice(m, c.off, c.n) != nil {
			t.Fatalf("accepted out-of-logical-range %v", c)
		}
	}
	if b := w.memSlice(m, 65532, 4); len(b) != 4 || cap(b) != 4 {
		t.Fatal("valid end/cap", len(b), cap(b))
	}
	if w.memSlice(m, 65536, 0) == nil {
		t.Fatal("empty buffer at end")
	}
	if w.memSlice(m, 65537, 0) != nil {
		t.Fatal("empty buffer past end")
	}
	AccessMemory(m, func(b []byte) {
		if len(b) != 65536 || cap(b) != 65536 {
			t.Fatal("host window exceeds logical size")
		}
	})
	for i := 65504; i < 65536; i++ {
		mem[i] = 'x'
	}
	if _, ok := w.readCStr(m, 65504); ok {
		t.Fatal("C string scan crossed logical end")
	}
	mem[65535] = 0
	if s, ok := w.readCStr(m, 65504); !ok || len(s) != 31 {
		t.Fatal("valid C string", s, ok)
	}
	for _, check := range []struct {
		name string
		call func() int32
	}{
		{"random crossing", func() int32 { return w.Random_get(m, 65535, 2) }},
		{"random past end", func() int32 { return w.Random_get(m, 65536, 1) }},
		{"random unsigned overflow", func() int32 { return w.Random_get(m, -1, 2) }},
		{"clock crossing", func() int32 { return w.Clock_time_get(m, 0, 0, 65532) }},
		{"args output crossing", func() int32 { return w.Args_sizes_get(m, 65534, 0) }},
		{"env output crossing", func() int32 { return w.Environ_sizes_get(m, 0, 65534) }},
		{"fd output crossing", func() int32 { return w.Fd_fdstat_get(m, 1, 65520) }},
		{"iovec table crossing", func() int32 { return w.Fd_write(m, 1, 65532, 1, 0) }},
	} {
		t.Run(check.name, func(t *testing.T) {
			if rc := check.call(); rc != _wasiEFAULT {
				t.Fatalf("errno %d, want EFAULT", rc)
			}
		})
	}
	// A valid vector header pointing outside logical memory must reject its data.
	binary.LittleEndian.PutUint32(mem[64:], 65536)
	binary.LittleEndian.PutUint32(mem[68:], 1)
	if rc := w.Fd_write(m, 1, 64, 1, 0); rc != _wasiEFAULT {
		t.Fatal("iovec buffer", rc)
	}
	if mem[65536] != 0 {
		t.Fatal("invalid imports changed tail")
	}
	base := m.M
	if MemoryGrow(m, 1) != 1 || m.M != base {
		t.Fatal("grow/stable pointer")
	}
	if rc := w.Random_get(m, 65536, 1); rc != 0 {
		t.Fatal("newly grown import buffer", rc)
	}
	AccessMemory(m, func(b []byte) {
		if len(b) != 2*65536 || cap(b) != 2*65536 {
			t.Fatal("grown host window")
		}
	})
	if MemoryGrow(m, 1) != -1 || size.Load() != 2*65536 {
		t.Fatal("failed grow changed logical bound")
	}
}
