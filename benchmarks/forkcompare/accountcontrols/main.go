package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	p7 "github.com/masahitojp/mariamem/internal/generatedgo/code/p7"
	p8 "github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
	"os"
	"sync/atomic"
	"unsafe"
)

func module() *base.Module {
	b := make([]byte, 32<<20)
	size := new(atomic.Uint64)
	size.Store(uint64(len(b)))
	return &base.Module{Memory: b, M: unsafe.Pointer(&b[0]), MemSize: size, MemShared: true, MaxMem: uint64(len(b)), Threads: &base.ThreadPool{}, T0: make([]any, 3)}
}
func put(m *base.Module, p int, v uint32) { binary.LittleEndian.PutUint32(m.Memory[p:], v) }
func need(ok bool, s string) {
	if !ok {
		panic(s)
	}
}
func main() {
	result := map[string]any{"result": "PASS", "fixed": base.ExperimentWaitAccounting}
	for _, nonnull := range []bool{false, true} {
		m := module()
		begin, end := 0, 0
		put(m, 392, 1024)
		put(m, 1024, 2048)
		put(m, 2064, 1)
		put(m, 2068, 2)
		m.T0[1] = func(*base.Module, int32) { begin++ }
		m.T0[2] = func(*base.Module, int32) { end++ }
		trx := int32(0)
		if nonnull {
			trx = 8192
		}
		p8.Fn16786(m, 4096, trx)
		want := 0
		if nonnull || base.ExperimentWaitAccounting {
			want = 1
		}
		need(begin == want && end == want && m.ExcPending == 0, "unbalanced read accounting")
		result[fmt.Sprint("nonnull_", nonnull)] = map[string]int{"begin": begin, "end": end}
	}
	m := module()
	p8.Fn16582(m)
	p8.Fn16583(m)
	need(m.ExcPending == 0, "nonpool wrapper guard")
	result["no_pool_guard"] = true
	m = module()
	put(m, 392, 1024)
	put(m, 396, 12288)
	put(m, 1024, 2048)
	put(m, 2064, 1)
	put(m, 2068, 2)
	put(m, 12288+64, 2)
	m.T0[1] = func(m *base.Module, p int32) { p7.Fn16605(m, p) }
	m.T0[2] = func(m *base.Module, p int32) { p8.Fn16606(m, p) }
	p8.Fn16582(m)
	p8.Fn16583(m)
	need(binary.LittleEndian.Uint32(m.Memory[1024+372:]) == 0 && m.Memory[12288+64] == 2 && m.ExcPending == 0, "long-task guard")
	result["long_task_guard"] = true
	if e := json.NewEncoder(os.Stdout).Encode(result); e != nil {
		panic(e)
	}
}
