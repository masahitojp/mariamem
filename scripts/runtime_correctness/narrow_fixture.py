"""Real Wasm opcode oracle for the platform-bound narrow atomic installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))
from runtime_atomic_loads import apply
sys.path.insert(0, str(ROOT / "benchmarks/spikes/generated-go-integration"))
from translate_guest import PATCHES

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def u(n):
    b=[]
    while n>=128:b.append((n&127)|128);n>>=7
    return bytes(b+[n])
def vec(xs):return u(len(xs))+b"".join(xs)
def sec(k,b):return bytes([k])+u(len(b))+b
def typ(ps,rs):return b"\x60"+vec([bytes([v]) for v in ps])+vec([bytes([v]) for v in rs])

def fixture():
    types=[typ([0x7f],[0x7f]),typ([0x7f],[0x7e]),typ([0x7f,0x7f],[]),
           typ([0x7f,0x7e],[]),typ([0x7f,0x7f],[0x7f]),typ([0x7f,0x7e],[0x7e]),
           typ([0x7f,0x7f,0x7f],[0x7f]),typ([0x7f,0x7e,0x7e],[0x7e]),typ([],[])]
    ops=[]
    for result in (32,64):
        for bits in (8,16):
            i=(2 if result==64 else 0)+(bits==16)
            ops.extend([{"name":f"Load{result}_{bits}","op":"load","bits":bits,"result":result,"code":0x12+i,"type":result==64,"argc":1},
                        {"name":f"Store{result}_{bits}","op":"store","bits":bits,"result":result,"code":0x19+i,"type":2+(result==64),"argc":2}])
            for j,op in enumerate(("add","sub","and","or","xor","xchg")):
                ops.append({"name":f"{op.title()}{result}_{bits}","op":op,"bits":bits,"result":result,"code":0x20+7*j+i,"type":4+(result==64),"argc":2})
            ops.append({"name":f"Cmp{result}_{bits}","op":"cmp","bits":bits,"result":result,"code":0x4a+i,"type":6+(result==64),"argc":3})
    for result in (32,64):
        i=result==64
        for op,opcode,ty,argc in (("load",0x10,0,1),("store",0x17,2,2),("add",0x1e,4,2),("cmp",0x48,6,3)):
            ops.append({"name":f"{op.title()}{result}","op":op,"bits":result,"result":result,"code":opcode+i,"type":ty+i,"argc":argc})
    bodies=[]
    for op in ops:
        code=b"".join(b"\x20"+u(i) for i in range(op["argc"]))+b"\xfe"+u(op["code"])+u({8:0,16:1,32:2,64:3}[op["bits"]])+u(0)
        bodies.append(u(len(code)+2)+b"\0"+code+b"\x0b")
    pad=b"\x01"*(1<<20)
    bodies.append(u(len(pad)+2)+b"\0"+pad+b"\x0b")
    exports=[u(len(op["name"]))+op["name"].encode()+b"\0"+u(i) for i,op in enumerate(ops)]
    exports.append(b"\x06memory\x02\0")
    wasm=b"\0asm\x01\0\0\0"+sec(1,vec(types))+sec(3,vec([u(int(op["type"])) for op in ops]+[u(8)]))+sec(5,b"\x01\x03\x01\x02")+sec(7,vec(exports))+sec(10,vec(bodies))
    cases=[]
    for op in ops:
        width=op["bits"]//8;mask=(1<<op["bits"])-1
        for addr in list(range(64,72,width))+[65536-width,65536,-1]+([65] if width>1 else []):
            for old in (0,0x91ff,mask):
                args=[] if op["argc"]==1 else ["ffffffffffffff12"]
                if op["argc"]==3:args=[format(old|(((1<<64)-1)^mask),"x"),"ffffffffffffff12"]
                cases.append({**op,"addr":addr,"initial":format(old,"x"),"args":args})
                if op["argc"]==3:cases.append({**op,"addr":addr,"initial":format(old,"x"),"args":[format((old+1)&mask,"x"),"ffffffffffffff12"]})
    return wasm,ops,cases

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--converter",type=Path)
    group.add_argument("--converter-archive",type=Path)
    p.add_argument("--converter-manifest",type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pins=json.loads((ROOT/"release/generated-go-translation.json").read_text())
    env=dict(os.environ,GOTOOLCHAIN="go1.26.10",GOWORK="off",GOENV="off",GOFLAGS="",GOEXPERIMENT="")
    if a.converter_archive:
        assert digest(a.converter_archive)==pins["converter_archive_sha256"]
        archive=out/"converter-source";archive.mkdir()
        with tarfile.open(a.converter_archive) as tar:tar.extractall(archive,filter="data")
        source=next(archive.iterdir());subprocess.run(["git","init","-q"],cwd=source,check=True)
        assert set(PATCHES)==set(pins["patches_sha256"])
        for name in PATCHES:
            patch=ROOT/"benchmarks/spikes/wasm2go"/name
            assert digest(patch)==pins["patches_sha256"][name]
            subprocess.run(["git","apply","--unidiff-zero",str(patch)],cwd=source,check=True)
        converter=out/"wasm2go"
        subprocess.run(["go","build","-mod=readonly","-trimpath","-buildvcs=false","-o",str(converter),"./cmd/wasm2go"],cwd=source,env=env,check=True)
        identity={k:pins[k] for k in ("converter_commit","converter_archive_sha256","patches_sha256")}
        identity["patched_converter_sha256"]=digest(converter)
    else:
        assert a.converter_manifest,"converter manifest required"
        identity=json.loads(a.converter_manifest.read_text())
        for k in ("converter_commit","converter_archive_sha256","patches_sha256"):assert identity[k]==pins[k]
        converter=a.converter.resolve();assert digest(converter)==identity["patched_converter_sha256"]
    wasm,ops,cases=fixture();path=out/"fixture.wasm";path.write_bytes(wasm)
    (out/"cases.json").write_text(json.dumps(cases))
    reference=subprocess.run(["node",str(HERE/"narrow_reference.js"),str(path),str(out/"cases.json")],capture_output=True,text=True,check=True)
    (out/"reference-results.json").write_text(reference.stdout)
    module=out/"module";module.mkdir();(module/"go.mod").write_text("module example.com/narrowfixture\n\ngo 1.26.0\n")
    target=module/"fixture"
    subprocess.run([str(converter),"-pure","-i",str(path),"-out-dir",str(target),"-pkg","fixture","-import","example.com/narrowfixture/fixture"],check=True)
    base=target/"base";raw=(base/"base.go").read_text();(base/"base.go").write_text(apply(raw))
    for template in HERE.glob("narrow_*"):
        if not template.name.endswith((".go.txt",".s.txt")) or "_test.go" in template.name:continue
        shutil.copyfile(template,base/template.name.removesuffix(".txt"))
    shutil.copyfile(ROOT/"internal/generatedgo/code/base/memory_mapping.go",base/"memory_mapping.go")
    driver=(ROOT/"tests/fixtures/narrow-atomic-driver.go.txt").read_text()
    entries=[]
    for op in ops:
        args=["m","addr"]+[f"int{op['result']}(a[{i}])" for i in range(op["argc"]-1)]
        call=op["name"]+"("+",".join(args)+")"
        body=call+";return 0" if op["op"]=="store" else "return uint64("+("uint32("+call+")" if op["result"]==32 else call)+")"
        entries.append('"'+op["name"]+'":func(m *base.Module,addr int32,a []uint64)uint64{'+body+"},")
    (target/"narrow_fixture_test.go").write_text(driver.replace("/*REGISTRY*/","\n".join(entries)))
    shutil.copyfile(out/"reference-results.json",target/"reference-results.json")
    rows=[]
    for backing in ("heap","mmap"):
        for race in (False,True):
            name=backing+("-race" if race else "")
            r=subprocess.run(["go","test","-p","1",*(["-race"] if race else []),"-count=1","-v","./fixture"],cwd=module,env={**env,"FIXTURE_BACKING":backing},capture_output=True,text=True,timeout=180)
            log=r.stdout+r.stderr;(out/(name+".txt")).write_text(log)
            rows.append({"name":name,"exit_code":r.returncode,"race_reports":log.count("WARNING: DATA RACE"),"log_sha256":hashlib.sha256(log.encode()).hexdigest()})
            if r.returncode:raise RuntimeError(log)
            print(name,"PASS",len(cases),"Wasm reference cases",flush=True)
    report={"wasm_sha256":digest(path),"reference_sha256":digest(out/"reference-results.json"),"cases":len(cases),
            "converter":identity,"exported_operations":ops,"raw_base_sha256":hashlib.sha256(raw.encode()).hexdigest(),
            "adapted_base_sha256":digest(base/"base.go"),"checks":rows,
            "go_version":subprocess.check_output(["go","version"],env=env,text=True).strip(),
            "reference_engine":subprocess.check_output(["node","--version"],text=True).strip(),
            "owner_sha256":{str(x.relative_to(ROOT)):digest(x) for x in [ROOT/"scripts/runtime_atomic_loads.py",HERE/"narrow_reference.js",ROOT/"tests/fixtures/narrow-atomic-driver.go.txt",*HERE.glob("narrow_*.go.txt"),*HERE.glob("narrow_*.s.txt")]},
            "scope":"Real memory32 Wasm exports, i32/i64 values, all narrow families plus full-width controls; no general mixed-access proof"}
    (out/"results.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":main()
