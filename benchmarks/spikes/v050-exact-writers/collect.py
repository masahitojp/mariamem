"""Preserve compact study receipts; copied text paths are normalized explicitly."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser()
p.add_argument("--task",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
task=a.task.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest={}
seen=set()
sources=[task/"temp/candidate-final/results.json",task/"temp/candidate-installation.json",
         task/"temp/observed-independent-installation.json"]
sources+=list((task/"temp/candidate-final").glob("*.txt"))
sources+=list((task/"evidence").glob("*.json"))+list((task/"evidence").glob("*.txt"))
for source in sources:
    target=out/source.name
    assert target.name not in seen,"duplicate evidence name"
    seen.add(target.name)
    text=source.read_text().replace(str(task),"$TASK")
    text=text.replace(str(Path.home())+"/","$USERHOME/")
    text="\n".join(line.rstrip() for line in text.splitlines())+("\n" if text else "")
    target.write_text(text)
    manifest[target.name]={"raw_sha256":digest(source),"saved_sha256":digest(target),
                           "path_normalization":"task/user-home prefixes replaced and trailing whitespace trimmed; raw and saved hashes recorded"}
host={}
for name in ("control-host","candidate-host"):
    host[name]=digest(task/"temp"/name)
identity={
 "baseline_source_commit":"753a015b9affa9fd8d19cff34e68feec7eabe5ae",
 "starting_fix_commit":"82f3c2bcef1518dadf5138a03e11dcfeb3db2de6",
 "guest_sha256":json.loads((ROOT/"release/generated-go-inputs.json").read_text())["guest_sha256"],
 "host_binary_sha256":host,
 "standalone_binary_sha256":{name:digest(task/"temp/candidate-final"/name) for name in ("native.test","linux-amd64.test")},
 "canonical_provenance_sha256":digest(ROOT/"internal/generatedgo/provenance.json"),
 "source_templates":{x.name:digest(x) for x in Path(__file__).parent.glob("*.txt")},
 "host_build_flags":"GOTOOLCHAIN=go1.26.8 go build -p 1 -buildvcs=false; source identity is recorded independently",
 "ownership":"Prototype only; canonical generator/inputs/output/provenance unchanged. Candidate rejects canonical verifier. Independent adapter output identity matched.",
 "saved_files":manifest,
}
(out/"identity.json").write_text(json.dumps(identity,indent=2)+"\n")
print("PASS:",len(manifest),"compact evidence files")
