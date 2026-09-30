#!/usr/bin/env python3
"""Attempt unchanged guest conversion; preserve the first failure and code size."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--guest',type=Path,required=True)
    p.add_argument('--converter',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--entry-exports')
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    generated=out/'generated'
    if generated.exists():p.error('use an unused output directory to avoid stale generation')
    # Isolate even incomplete converter output from the product's go test ./....
    (out/'go.mod').write_text('module example.com/mariamem-spike\n\ngo 1.26.0\n')
    cmd=[str(a.converter.resolve()),'-pure','-i',str(a.guest.resolve()),'-out-dir',str(generated),
         '-pkg','generated','-import','example.com/mariamem-spike/generated']
    if a.entry_exports:cmd+=['-entry-exports',a.entry_exports]
    start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
    report=dict(guest_sha256=hashlib.sha256(a.guest.read_bytes()).hexdigest(),
                converter_sha256=hashlib.sha256(a.converter.read_bytes()).hexdigest(),
                entry_exports=a.entry_exports,seconds=time.monotonic()-start,exit_code=r.returncode,
                stdout=r.stdout,stderr=r.stderr,
                generated_files=sum(f.is_file() for f in generated.rglob('*')) if generated.exists() else 0,
                generated_bytes=sum(f.stat().st_size for f in generated.rglob('*') if f.is_file()) if generated.exists() else 0)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
