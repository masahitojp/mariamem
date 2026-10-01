#!/usr/bin/env python3
"""Create a private module importing unchanged mariamem host/wire packages."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--guest',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[3]
    out=a.output_dir.resolve();probe=a.probe.resolve();guest=a.guest.resolve()
    digest=hashlib.sha256(guest.read_bytes()).hexdigest()
    assert digest=='6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3'
    out.mkdir(parents=True,exist_ok=True)
    assert not (out/'go.mod').exists(), 'use a fresh output directory'
    import os
    relative=os.path.relpath(repo,out)
    (out/'go.mod').write_text('module github.com/masahitojp/mariamem/benchmarks/tail-wire\n\ngo 1.26.0\n\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+relative+'\n')
    (out/'main.go').write_text(Path(__file__).with_name('wire-boundary.go.txt').read_text())
    # Adapter changes only argv. Guest framing, SQL and host behavior are intact.
    adapter=out/'exec-guest.sh'
    adapter.write_text('#!/bin/sh\nexec '+shlex.quote(str(probe))+' measure\n');adapter.chmod(0o755)
    # Metadata describes the actual WASM, never the production AOT artifact.
    sidecar=Path(str(guest)+'.json')
    data=dict(wasm_sha256=digest,module_sha256=digest,snapshot_version=1)
    if sidecar.exists():assert json.loads(sidecar.read_text())==data
    else:sidecar.write_text(json.dumps(data)+'\n')
    (out/'pins.json').write_text(json.dumps(dict(probe_hash=hashlib.sha256(probe.read_bytes()).hexdigest(),runtime_hash=hashlib.sha256(adapter.read_bytes()).hexdigest()),indent=2)+'\n')


if __name__=='__main__':main()
