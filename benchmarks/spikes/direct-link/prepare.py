#!/usr/bin/env python3
"""Copy the canonical host adapter without editing production sources."""
import argparse, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
root=Path(__file__).resolve().parents[3]; out=a.output.resolve()
if not out.is_relative_to(root/"build") or out==root/"build":raise ValueError("output must be an isolated child of ignored build/")
out.mkdir(parents=True,exist_ok=True)
records={}
for name in ("main.go","guest_identity.go","entry.go"):
 src=root/"internal/generatedgo"/name; b=src.read_bytes(); records[name]=hashlib.sha256(b).hexdigest()
 (out/name).write_bytes(b.replace(b"package generatedgo",b"package main",1))
(out/"probe.go").write_bytes((Path(__file__).parent/"probe.go.txt").read_bytes())
(out/"go.mod").write_text("module github.com/masahitojp/mariamem/directlinkprobe\n\ngo 1.26.0\n\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => "+str(root)+"\n")
(out/"inputs.json").write_text(json.dumps(records,indent=2)+"\n")
