package inlineprobe
import "sync/atomic"
type Module struct{MemSize atomic.Uint64}
//go:noinline
func trap(){panic("oob")}
func Bounds(m *Module,a,o,s uint64)bool{b:=m.MemSize.Load();return a<=b&&o<=b-a&&s<=b-a-o}
func Baseline(m *Module,a,o,s uint64)uint64{if !Bounds(m,a,o,s){trap()};return a+o}
func Candidate(m *Module,a,o,s uint64)uint64{if !Bounds(m,a,o,s){panic("wasm: memory access out of bounds")};return a+o}
