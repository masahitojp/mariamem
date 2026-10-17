#!/usr/bin/env python3
"""Preserve compact raw evidence, including the first collector failure."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace',type=Path)
    p.add_argument('initial_workspace',type=Path)
    args=p.parse_args()
    out=ROOT/'benchmarks/spikes/ownedroot/evidence'
    out.mkdir(exist_ok=True)
    pairs=[(args.workspace/'evidence'/n,n) for n in
           ('component.jsonl','existing-strict.jsonl','component-race.jsonl','receipt.json','g0-targeted.json','g0-targeted.jsonl')]
    pairs += [(args.workspace/'evidence/console.log','console.txt'),
              (args.initial_workspace/'evidence/console.log','initial-collector-failure.txt'),
              (args.initial_workspace/'evidence/component.jsonl','initial-component.jsonl')]
    records=[]
    for source,name in pairs:
        data=source.read_bytes()
        text=data.decode().replace(str(ROOT),'<source>')
        text=re.sub(r'/(?:Users|home)/[^\s/]+/', '<user>/', text)
        stored=text.encode();(out/name).write_bytes(stored)
        records.append({'file':name,'original_sha256':hashlib.sha256(data).hexdigest(),
                        'stored_sha256':hashlib.sha256(stored).hexdigest(),
                        'normalization':'Personal paths only; JSON numbers and trial/test events retained.'})
    (out/'files.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Preserved',len(records),'raw evidence files.')

if __name__=='__main__':main()
