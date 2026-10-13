"""Supplementary amd64 instruction execution on an arm64 Docker host, not native qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--task", type=Path, required=True)
a = p.parse_args()
task = a.task.resolve()
image = "sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f"
binary = task / "temp/candidate-final/linux-amd64.test"
rows = []
for backing in ("heap","mmap"):
    cmd = ["docker","run","--rm","--network","none","-v",str(binary.parent)+":/study:ro",
           "--entrypoint","/study/linux-amd64.test","-e","BACKING="+backing,image,
           "-test.v","-test.run","^Test(ValuesAndBounds|DisjointOrdinaryNeighbor|SameTargetAtomic|MixedSizeAtomic|SCStoreBuffering|SCIRIW|MixedWidthSC|Publication)$"]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    log = r.stdout+r.stderr
    (task / "evidence" / ("linux-amd64-emulated-"+backing+".txt")).write_text(log)
    rows.append({"backing":backing,"exit_code":r.returncode,"log_sha256":hashlib.sha256(log.encode()).hexdigest()})
    assert r.returncode==0,log
    print(backing,"PASS")
(task / "evidence/linux-amd64-emulated.json").write_text(json.dumps({
    "image":image,"image_platform":"linux/arm64","binary_platform":"linux/amd64",
    "host":"macOS arm64; amd64 binary executed through container emulation",
    "native_ubuntu_x86_64":"SKIP: no native runner; this does not replace it",
    "binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"checks":rows,
},indent=2)+"\n")
