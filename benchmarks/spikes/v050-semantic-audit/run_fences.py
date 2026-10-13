"""Reproduce the bounded sysroot/optimizer/converter fence-stage observations.

Not a rebuild of the adopted guest: the reduction linker is LLVM 21.1.2.
All outputs must be disposable. Source/patch acquisition is described in README.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f"
FLAGS = ["-O2", "--enable-threads", "--enable-mutable-globals", "--enable-bulk-memory",
         "--enable-bulk-memory-opt", "--enable-exception-handling", "--enable-simd",
         "--enable-relaxed-simd", "--enable-extended-const"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("output", "evidence", "converter", "converter-source", "libc"):
        p.add_argument("--"+arg, type=Path, required=True)
    a = p.parse_args()
    for key,value in vars(a).items():
        setattr(a,key,value.resolve())
    a.output.mkdir(parents=True, exist_ok=False)
    a.evidence.mkdir(parents=True, exist_ok=True)
    commands = []
    env = dict(os.environ, GOTOOLCHAIN="go1.26.8")

    def run(cmd, cwd=None):
        cmd = list(map(str,cmd))
        result = subprocess.run(cmd,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        commands.append({"command":cmd,"cwd":str(cwd) if cwd else None,"exit_code":result.returncode,
                         "stdout":result.stdout,"stderr":result.stderr})
        (a.evidence/"fence-checkpoint.json").write_text(json.dumps(commands,indent=2)+"\n")
        result.check_returncode()
        return result.stdout

    run([sys.executable,HERE/"fences.py","--output",a.output,"--libc",a.libc])
    prefix = ["docker","run","--rm","-v",str(a.output)+":/work","-w","/work","--entrypoint"]
    ld = "/root/.wasixcc/llvm/bin/wasm-ld"
    opt = "/root/.wasixcc/binaryen/bin/wasm-opt"
    versions = {"lld":run([*prefix,ld,IMAGE,"--version"]).strip(),
                "binaryen":run([*prefix,opt,IMAGE,"--version"]).strip(),
                "go":run(["go","version"]).strip()}
    run([*prefix,ld,IMAGE,"--no-entry","--allow-undefined","--shared-memory",
         "--export=__tl_unlock","--export=__tl_sync","pthread_create.o","-o","linked.wasm"])
    run([*prefix,opt,IMAGE,*FLAGS,"linked.wasm","-o","optimized.wasm"])
    decoder = a.converter_source/"cmd/audit-opcodes"
    decoder.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/"opcodes.go.txt",decoder/"main.go")
    decoded = run(["go","run","./cmd/audit-opcodes",a.output/"pthread_create.o",a.output/"pthread_join.o",
                   a.output/"linked.wasm",a.output/"optimized.wasm"],cwd=a.converter_source)
    rows = [json.loads(s) for s in decoded.splitlines()]
    counts = {Path(r["path"]).name:sum(len(f["fences"]) for f in r["functions"]) for r in rows}
    assert counts["linked.wasm"] == 3 and counts["optimized.wasm"] == 0, counts
    single,multi = a.output/"single",a.output/"multi"
    single.mkdir()
    run([a.converter,"-pure","-i",a.output/"fence.wasm","-import","example.com/fence","-pkg","generated","-o",single/"fence.go"])
    run([a.converter,"-pure","-keep-dead-funcs","-i",a.output/"fence-multi.wasm","-import","example.com/fence","-pkg","generated","-out-dir",multi])
    sites = {key:[{"file":str(f.relative_to(a.output)),"line":n,"statement":s.strip()}
                  for f in sorted(directory.rglob("*.go")) for n,s in enumerate(f.read_text().splitlines(),1)
                  if "= atomicFence(m)" in s or "= base.AtomicFence(m)" in s]
             for key,directory in (("single",single),("multi",multi))}
    assert all(len(v)==1 for v in sites.values()),sites
    result = {"image_id":IMAGE,"versions":versions,"commands":commands,"decoded":rows,"fence_counts":counts,
              "converter_fence_sites":sites,"converter_binary_sha256":sha(a.converter),"libc_sha256":sha(a.libc),
              "decoder_sha256":sha(HERE/"opcodes.go.txt"),
              "output_sha256":{str(f.relative_to(a.output)):sha(f) for f in sorted(a.output.rglob("*")) if f.is_file()},
              "scope":"small pinned-libc link/optimization reduction and converter fixtures; no full adopted-guest build"}
    (a.evidence/"fence-results.json").write_text(json.dumps(result,indent=2)+"\n")
    print("PASS stage observation:",counts,"; explicit converter fences preserved in both modes")


if __name__ == "__main__":
    main()
