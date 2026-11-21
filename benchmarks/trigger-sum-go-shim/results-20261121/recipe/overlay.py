"""Fold constant displacement + access width at generation time for memory32."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys

w=Path(sys.argv[1]).resolve()
src=w/'worktree/internal/generatedgo/code'
t=w/'temp'
directory=t/'overlay'
directory.mkdir(exist_ok=True)
paths={}
def save(original,content):
    file=directory/original.name
    file.write_text(content)
    paths[str(original)]=str(file)
base=src/'base/base.go'
anchor='// atomicEA bounds- and alignment-checks'
s=base.read_text()
assert s.count(anchor)==1
helper="""// CheckedMemory32 checks one generated access whose constant end is offset + width.
// The caller adds the original constant displacement to the returned address.
//go:noinline
func CheckedMemory32(m *Module, addr, end uint32) uint64 {
    if uint64(addr)+uint64(end) > m.MemSize.Load() {
        panic("wasm: memory access out of bounds")
    }
    return uint64(addr)
}

"""
save(base,s.replace(anchor,helper+anchor))
pattern=re.compile(r'base\.MemoryEA\(m, (uint64\(uint32\(([^\n]*?)\)\)|\d+), (\d+), (\d+)\)')
bases=collections.Counter(); widths=collections.Counter(); end_max=0
def apply(m):
    global end_max
    addr,expr,offset,width=m.groups()
    offset,width=int(offset),int(width)
    assert width>0 and offset+width<=0xffffffff
    if expr is None:
        assert int(addr)<=0xffffffff
        bases['constant']+=1
    else:
        assert 'base.MemoryEA' not in expr
        addr='uint32('+expr+')'
        bases['memory32']+=1
    widths[width]+=1
    end_max=max(end_max,offset+width)
    value=f'base.CheckedMemory32(m, {addr}, {offset+width})'
    return f'({value} + {offset})' if offset else value
for path in sorted(src.rglob('*_pure.go')):
    orig=path.read_text()
    updated,n=pattern.subn(apply,orig)
    assert n==orig.count('base.MemoryEA(m,'),path
    if n: save(path,updated)
assert bases=={'constant':51161,'memory32':860176}
(t/'overlay.json').write_text(json.dumps({'Replace':paths}))
(w/'evidence/published/binding.json').write_text(json.dumps(dict(
    bases=bases,widths=widths,max_displacement_plus_width=end_max,
    files={str(Path(p).relative_to(src)):dict(source=hashlib.sha256(Path(p).read_bytes()).hexdigest(),
        overlay=hashlib.sha256(Path(o).read_bytes()).hexdigest()) for p,o in paths.items()}),indent=2)+'\n')
