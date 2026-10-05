//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"testing"
)

func TestMappedHostImportLogicalBuffers(t *testing.T) {
	h := mappedTestHost()
	m, release, e := newMemoryModule(h)
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	end := int32(generated.InitialMemoryBytes)
	checks := []func() int32{
		func() int32 { return h.Random_get(m, end, 1) },
		func() int32 { return h.Random_get(m, end-1, 2) },
		func() int32 { return h.Random_get(m, -1, 1) },
		func() int32 { return h.Clock_time_get(m, 0, 0, end-4) },
		func() int32 { return h.Args_sizes_get(m, end-2, 0) },
		func() int32 { return h.Environ_sizes_get(m, 0, end-2) },
		func() int32 { return h.Fd_fdstat_get(m, 1, end-16) },
		func() int32 { return h.Fd_write(m, 1, end-4, 1, 0) },
	}
	for i, f := range checks {
		if rc := f(); rc != 21 {
			t.Fatalf("import %d errno=%d, expected WASI EFAULT", i, rc)
		}
	}
	base.AccessMemory(m, func(b []byte) {
		if len(b) != int(generated.InitialMemoryBytes) || cap(b) != len(b) {
			t.Fatal("reserved tail exposed")
		}
	})
	ptr := m.M
	if base.MemoryGrow(m, 1) != 4096 || m.M != ptr {
		t.Fatal("grow")
	}
	if m.Memory[end] != 0 {
		t.Fatal("new range not zero")
	}
	if rc := h.Random_get(m, end, 1); rc != 0 {
		t.Fatal("grown import", rc)
	}
	if rc := h.Random_get(m, end+65536, 1); rc != 21 {
		t.Fatal("new logical end", rc)
	}
	if base.MemoryGrow(m, 32768-4097) != 4097 {
		t.Fatal("grow max")
	}
	callback := "__wasm_signal"
	copy(m.Memory[(2<<30)-len(callback):], callback)
	h.Callback_signal(m, int32((2<<30)-len(callback)), int32(len(callback)))
	if h.signalCallback != callback {
		t.Fatal("valid max-end host slice")
	}
	if e := release(); e != nil {
		t.Fatal(e)
	}
	if e := release(); e != nil {
		t.Fatal(e)
	}
	t.Log("invalid imports returned EFAULT without touching PROT_NONE; grow and repeated release pass")
}
