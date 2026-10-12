"""Reproducible disposable host candidate; canonical source must remain unchanged.

This adapter is an experiment owner, not a production installer. It checks the
canonical input hash, rejects unknown helper shapes, copies the tree, and records
every change. Full canonical regeneration is a separate adoption step.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
a = parser.parse_args()
root = a.source.resolve()
out = a.output.resolve()
assert not out.exists()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source = root / "internal/generatedgo"
record = json.loads((source / "provenance.json").read_text())
base = source / "code/base/base.go"
assert digest(base) == record["files_sha256"]["code/base/base.go"]
old = base.read_text()
pattern = r"func AtomicSubword32\(m \*Module, ea uint64, bits uint, op func\(old uint32\) uint32\) uint32 \{.*?\n\}"
matches = list(re.finditer(pattern, old, re.S))
assert len(matches) == 1
body = """func AtomicSubword32(m *Module, ea uint64, bits uint, op func(old uint32) uint32) uint32 {
 p := unsafe.Add(m.M, uintptr(ea))
 read, compare := exactWriterRead8, exactWriterCmp8
 if bits == 16 { read, compare = exactWriterRead16, exactWriterCmp16 } else if bits != 8 { panic("writer width") }
 mask := uint32(1)<<bits - 1
 old := read(p)
 for {
  seen := compare(p, old, op(old)&mask)
  if seen == old { return old }
  old = seen
 }
}"""
text = old[:matches[0].start()] + body + old[matches[0].end():]
for bits,width in ((8,1),(16,2)):
    before = (f"func AtomicStore32_{bits}(m *Module, addr int32, offset int32, v int32) int32 {{\n"
              f"\tAtomicSubword32(m, AtomicEA(m, addr, offset, {width}), {bits}, func(uint32) uint32 {{ return uint32(v) }})\n"
              "\treturn 0\n}")
    assert text.count(before) == 1
    after = (f"func AtomicStore32_{bits}(m *Module, addr int32, offset int32, v int32) int32 {{\n"
             f" exactWriterWrite{bits}(unsafe.Add(m.M, uintptr(AtomicEA(m, addr, offset, {width}))), uint32(v))\n"
             " return 0\n}")
    text = text.replace(before, after)
shutil.copytree(root, out, ignore=shutil.ignore_patterns(".git", "build", "__pycache__", ".pytest_cache"))
target = out / "internal/generatedgo/code/base"
(target / "base.go").write_text(text)
rename = {f"{op}{bits}":f"exactWriter{verb}{bits}" for op,verb in (("read","Read"),("write","Write"),("cmp","Cmp")) for bits in (8,16)}
decl = (HERE / "ops.go.txt").read_text().split("func mask",1)[0].replace("package narrow","package base",1)
for name,replacement in rename.items():
    decl = re.sub(r"\b"+name+r"\b",replacement,decl)
(target / "experimental_exact_writers.go").write_text(decl)
for arch in ("arm64","amd64"):
    asm = (HERE / f"ops_{arch}.s.txt").read_text()
    for name,replacement in rename.items():
        asm = asm.replace("·"+name+"(SB)","·"+replacement+"(SB)")
    (target / f"experimental_exact_writers_{arch}.s").write_text(asm)
manifest = {
    "contract":"disposable-exact-writer-candidate",
    "guest_sha256":record["guest_sha256"],
    "baseline_base_sha256":digest(base),
    "adapted_base_sha256":digest(target / "base.go"),
    "templates":{p.name:digest(p) for p in HERE.glob("ops*.txt")},
    "added_files":{p.name:digest(p) for p in target.glob("experimental_exact_writers*")},
    "ownership":"Canonical verifier must reject this disposable copy. No provenance refreshed; no product adoption."
}
(out.parent / (out.name + "-installation.json")).write_text(json.dumps(manifest,indent=2)+"\n")
print("PASS: isolated hash-bound candidate adapter")
