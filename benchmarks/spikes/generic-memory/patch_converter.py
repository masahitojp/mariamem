#!/usr/bin/env python3
"""Opt-in disposable generic rule. Never edits an individual generated function."""
from pathlib import Path
import sys
r=Path(sys.argv[1])
p=r/'internal/codegen/translate.go';s=p.read_text();s=s.replace('PureOnly bool','PureOnly bool\n\tCheckedMemory bool // experiment: logical bounds before every scalar/inline atomic access')
s=s.replace('if pass.FoldMemAddend(ssaFn, largeConstThreshold) {','if !t.opts.CheckedMemory && pass.FoldMemAddend(ssaFn, largeConstThreshold) {')
p.write_text(s)
import re
p=r/'cmd/wasm2go/main.go';s=p.read_text().replace('flag.Parse()', 'checkedMemory := flag.Bool("checked-memory", false, "experiment: check logical bounds for pure-Go memory accesses")\n\tflag.Parse()')
s=re.sub(r'(PureOnly:\s*\*pureOnly,)',r'\1\n\t\tCheckedMemory: *checkedMemory,',s);p.write_text(s)
p=r/'internal/codegen/emit_memops.go';s=p.read_text();needle="""	em.useImport("unsafe")
	added := &ast.CallExpr{"""
# Only unsafeDerefExpr (first occurrence), keep typed-pointer load/store model.
replacement="""	em.useImport("unsafe")
	address := em.memOffsetExpr(baseExpr, offset, baseVal)
	if em.t != nil && em.t.opts.CheckedMemory {
		em.useHelper("memoryEA")
		addr := ast.Expr(&ast.CallExpr{Fun:newID("uint64"),Args:[]ast.Expr{baseExpr}})
		if !em.mem64 {
			addr = &ast.CallExpr{Fun:newID("uint64"),Args:[]ast.Expr{&ast.CallExpr{Fun:newID("uint32"),Args:[]ast.Expr{baseExpr}}}}
			if c := ssaConstBase(baseVal); c != nil { addr = uintLit(uint64(uint32(c.AuxInt))) }
		} else if c := ssaConstBase64(baseVal); c != nil { addr = uintLit(uint64(c.AuxInt)) }
		width := map[string]uint64{"uint8":1,"int8":1,"uint16":2,"int16":2,"uint32":4,"int32":4,"float32":4,"int64":8,"uint64":8,"float64":8}[spec.elemType]
		if width == 0 { panic("unknown memory width") }
		address = &ast.CallExpr{Fun:em.helperRef("memoryEA"),Args:[]ast.Expr{newID("m"),addr,uintLit(offset),uintLit(width)}}
	}
	added := &ast.CallExpr{"""
assert s.count(needle)==1
s=s.replace(needle,replacement,1).replace('em.memBasePtrExpr(), em.memOffsetExpr(baseExpr, offset, baseVal)','em.memBasePtrExpr(), address',1)
# Inline atomics retain the native sync/atomic operation after checked EA/alignment.
needle="""	em.useImport("unsafe")
	em.useImport("sync/atomic")
	added := &ast.CallExpr{"""
replacement="""	em.useImport("unsafe")
	em.useImport("sync/atomic")
	address := em.memOffsetExpr(baseExpr, offU, v.Args[0])
	if em.t != nil && em.t.opts.CheckedMemory {
		name := "atomicEA"
		off := goConstI32(int32(offU))
		if em.mem64 { name="atomicEA64"; off=goConstI64(int64(offU)) }
		em.useHelper(name)
		width := uint64(4); if spec.elemType=="uint64" { width=8 }
		address=&ast.CallExpr{Fun:em.helperRef(name),Args:[]ast.Expr{newID("m"),baseExpr,off,uintLit(width)}}
	}
	added := &ast.CallExpr{"""
assert needle in s;s=s.replace(needle,replacement).replace('em.memOffsetExpr(baseExpr, offU, v.Args[0]),','address,',1);p.write_text(s)
p=r/'internal/codegen/helpers/helpers.go';s=p.read_text();pos=s.index('func memBound(')
s=s[:pos]+"""// memoryEA is the shared non-wrapping logical-bound rule. Subtractions make
// both additions safe, including memory64 without a representable 65-bit sum.
func memoryInBounds(m *Module, addr, offset, size uint64) bool {
	bound := m.memSize.Load()
	return addr <= bound && offset <= bound-addr && size <= bound-addr-offset
}
func memoryEA(m *Module, addr, offset, size uint64) uint64 {
	if !memoryInBounds(m,addr,offset,size) { wasm_trap_memory_oob() }
	return addr+offset
}
//go:noinline
func wasm_trap_memory_oob() { panic("wasm: memory access out of bounds") }

"""+s[pos:]
# The shared arithmetic/bounds core is common; atomic retains natural alignment.
s=s.replace("""	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	if ea+size > memBound(m) {
		wasm_trap_atomic_oob()
	}""","""	ea := uint64(uint32(addr))+uint64(uint32(offset))\n\tif !memoryInBounds(m,uint64(uint32(addr)),uint64(uint32(offset)),size) { wasm_trap_atomic_oob() }""")
s=s.replace("""	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	if ea+size > m.memSize.Load() {
		wasm_trap_simd_oob()
	}""","""	ea := uint64(uint32(addr))+uint64(uint32(offset))\n\tif !memoryInBounds(m,uint64(uint32(addr)),uint64(uint32(offset)),size) { wasm_trap_simd_oob() }""")
p.write_text(s)

# Trapping scalar loads must remain observable even if their result is dropped.
p=r/'internal/ssa/ssa.go';s=p.read_text().replace('type Value struct {','type Value struct {\n MemoryMayTrap bool // opt-in checked scalar loads are observable') ;p.write_text(s)
p=r/'internal/ssa/op.go';s=p.read_text().replace('if v.Op == OpAtomicCall {','if v.MemoryMayTrap { return true }\n\tif v.Op == OpAtomicCall {',1);p.write_text(s)
p=r/'internal/codegen/translate.go';s=p.read_text().replace('insBefore := ssa.CountValues(ssaFn)', 'if t.opts.CheckedMemory {\n for _,b := range ssaFn.Blocks { for _,v := range b.Values { if _,ok:=loadSpec(v);ok {v.MemoryMayTrap=true} } }\n }\n insBefore := ssa.CountValues(ssaFn)',1).replace('memOptOK := !t.memoryIsShared()', 'memOptOK := !t.memoryIsShared() && !t.opts.CheckedMemory');p.write_text(s)
