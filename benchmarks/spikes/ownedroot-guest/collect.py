#!/usr/bin/env python3
"""Preserve compact experiment evidence, retaining failed attempts and all trials."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parent/'evidence'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args();w=a.workspace.resolve();DEST.mkdir(exist_ok=True)
 files={};inputs=list((w/'evidence').rglob('*'))
 inputs+=[w/'temp/release-inputs/generated-release/regeneration.json']
 for source in inputs:
  if not source.is_file():continue
  name='canonical-regeneration.json' if source.name=='regeneration.json' else source.relative_to(w/'evidence').as_posix()
  raw=source.read_bytes();text=raw.decode()
  text=text.replace(str(ROOT),'<source>').replace(str(w/'temp'),'<temp>')
  text=re.sub(r'/(?:Users|home)/[^\s/]+/','<user>/',text)
  stored=text.encode();dest=DEST/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(stored)
  files[name]={'original_sha256':sha(raw),'stored_sha256':sha(stored),'bytes':len(stored)}
 (DEST/'files.json').write_text(json.dumps(files,indent=2,sort_keys=True)+'\n')
 print('preserved',len(files),'files',sum(x['bytes'] for x in files.values()),'bytes')
if __name__=='__main__':main()
