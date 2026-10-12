"""Native narrow atomic installation, owned here rather than in generated Go.

The module name predates writer adoption. The pinned converter is unchanged.
Only emitted 8/16-bit helpers are adapted; missing, duplicate, changed or
already-adapted definitions are rejected when their references are present.
Full-width operations and ordinary accesses retain their existing lowering.
"""
import re


SUBWORD = """func AtomicSubword32(m *Module, ea uint64, bits uint, op func(old uint32) uint32) uint32 {
	word := (*uint32)(unsafe.Add(m.M, uintptr(ea&^3)))
	shift := uint(ea&3) * 8
	mask := uint32(1)<<bits - 1
	if !AtomicsContended(m) {
		cur := *word
		lane := (cur >> shift) & mask
		*word = (cur &^ (mask << shift)) | ((op(lane) & mask) << shift)
		return lane
	}
	for {
		cur := atomic.LoadUint32(word)
		lane := (cur >> shift) & mask
		next := (cur &^ (mask << shift)) | ((op(lane) & mask) << shift)
		if atomic.CompareAndSwapUint32(word, cur, next) {
			return lane
		}
	}
}"""
NATIVE_SUBWORD = """func AtomicSubword32(m *Module, ea uint64, bits uint, op func(old uint32) uint32) uint32 {
	p := unsafe.Add(m.M, uintptr(ea))
	read, compare := atomicRead8At, atomicCmp8At
	if bits == 16 {
		read, compare = atomicRead16At, atomicCmp16At
	} else if bits != 8 {
		panic("mariamem: invalid narrow atomic width")
	}
	mask := uint32(1)<<bits - 1
	old := read(p)
	for {
		seen := compare(p, old, op(old)&mask)
		if seen == old {
			return old
		}
		old = seen
	}
}"""
CMP = """func AtomicCmpxchgSubword(m *Module, ea uint64, bits uint, expected, replacement uint32) uint32 {
	word := (*uint32)(unsafe.Pointer(&m.Memory[ea&^3]))
	shift := uint(ea&3) * 8
	mask := uint32(1)<<bits - 1
	for {
		cur := atomic.LoadUint32(word)
		lane := (cur >> shift) & mask
		if lane != expected&mask {
			return lane
		}
		next := (cur &^ (mask << shift)) | ((replacement & mask) << shift)
		if atomic.CompareAndSwapUint32(word, cur, next) {
			return lane
		}
	}
}"""
NATIVE_CMP = """func AtomicCmpxchgSubword(m *Module, ea uint64, bits uint, expected, replacement uint32) uint32 {
	p := unsafe.Add(m.M, uintptr(ea))
	switch bits {
	case 8:
		return atomicCmp8At(p, expected, replacement)
	case 16:
		return atomicCmp16At(p, expected, replacement)
	default:
		panic("mariamem: invalid narrow atomic width")
	}
}"""


def replace_helper(text, name, old, new):
    definitions = re.findall(r"(?m)^func " + re.escape(name) + r"\(", text)
    if not definitions:
        if re.search(r"\b" + re.escape(name) + r"\(", text):
            raise ValueError("narrow atomic definition missing: " + name)
        return text
    if len(definitions) != 1 or text.count(old) != 1:
        raise ValueError("narrow atomic converter shape changed: " + name)
    return text.replace(old, new, 1)


def apply(text):
    if not re.search(r"(?m)^func AtomicSubword32\(", text):
        raise ValueError("narrow atomic definition missing: AtomicSubword32")
    for result in (32, 64):
        for bits, width in ((8, 1), (16, 2)):
            name = f"AtomicLoad{result}_{bits}u"
            prefix = f"func {name}(m *Module, addr int32, offset int32) int{result} {{\n"
            old = (prefix + f"\treturn int{result}(AtomicSubword32(m, AtomicEA(m, addr, offset, {width}), {bits}, "
                   "func(old uint32) uint32 { return old }))\n}")
            new = prefix + f"\treturn int{result}(atomicRead{bits}At(unsafe.Add(m.M, uintptr(AtomicEA(m, addr, offset, {width})))))\n}}"
            text = replace_helper(text, name, old, new)
            name = f"AtomicStore{result}_{bits}"
            prefix = f"func {name}(m *Module, addr int32, offset int32, v int{result}) int32 {{\n"
            old = (prefix + f"\tAtomicSubword32(m, AtomicEA(m, addr, offset, {width}), {bits}, "
                   "func(uint32) uint32 { return uint32(v) })\n\treturn 0\n}")
            new = (prefix + f"\tatomicWrite{bits}At(unsafe.Add(m.M, uintptr(AtomicEA(m, addr, offset, {width}))), uint32(v))"
                   "\n\treturn 0\n}")
            text = replace_helper(text, name, old, new)
    text = replace_helper(text, "AtomicSubword32", SUBWORD, NATIVE_SUBWORD)
    text = replace_helper(text, "AtomicCmpxchgSubword", CMP, NATIVE_CMP)
    text = text.replace(
        "// atomicSubword32 runs op on the byte lanes [shift, shift+bits) of the\n"
        "// aligned 32-bit word containing ea, via a CAS loop; returns the OLD lane\n"
        "// value zero-extended. Little-endian lane math.",
        "// atomicSubword32 uses a native exact-width load/CAS loop at checked ea.\n"
        "// Only 8/16-bit operands are supported here; returns the OLD lane zero-extended.\n"
        "// Full-width atomics use their separate existing cores.")
    text = text.replace(
        "// atomicCmpxchgSubword is the compare-exchange counterpart of\n"
        "// atomicSubword32: CAS on the byte lanes [shift, shift+bits) of the aligned\n"
        "// 32-bit word containing the checked effective address ea.",
        "// atomicCmpxchgSubword compares/exchanges exactly 8 or 16 bits at checked ea.\n"
        "// The native primitive truncates operands and returns the old lane zero-extended.")
    return text
