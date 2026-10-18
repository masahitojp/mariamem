#!/usr/bin/env python3
"""Preserve compact text evidence and hashes; never execute a guest."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):return hashlib.sha256(data).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 work=a.workspace.resolve();source=work/'evidence';out=a.output;out.mkdir(parents=True,exist_ok=False)
 def scrub(text):
  return text.replace(str(work),'<workspace>').replace('/private/tmp/mariamem-child-control-clone','<control-clone>').replace('/private/tmp/mariamem-child-observed-clone','<observed-clone>').replace(str(Path.home())+'/', '<user-home>/')
 files={};profiles={}
 for path in sorted(source.rglob('*')):
  if not path.is_file():continue
  relative=path.relative_to(source).as_posix();raw=path.read_bytes()
  if relative.startswith('stamp-rejected-campaign/'):
   continue  # Retain locally; summarize the entire rejected campaign separately below.
  if path.suffix=='.pprof':
   profiles[relative]={'stored_path':stored_relative,'original_sha256':digest(raw),'original_bytes':len(raw),'retention':'compact local original; all merged samples in profile-*-raw.txt'};continue
  try:normalized=scrub(raw.decode()).encode()
  except UnicodeDecodeError:raise AssertionError('unexpected binary evidence: '+relative)
  stored_relative=relative[:-4]+'.txt' if relative.endswith('.log') else relative
  target=out/stored_relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(normalized)
  files[relative]={'stored_path':stored_relative,'original_sha256':digest(raw),'stored_sha256':digest(normalized),'original_bytes':len(raw),'stored_bytes':len(normalized)}
 rejected=source/'stamp-rejected-campaign'
 if rejected.exists():
  receipt=json.loads((rejected/'receipt.json').read_text())
  summary={'status':'REJECTED_FOR_PERFORMANCE_CONCLUSIONS','reason':'Go1.26.8 VCS-root lookup does not recognize linked-worktree .git files; all four stamps reported outer main, not measured source commits. Entire campaign excluded uniformly, not based on timing. Original compact cells retained locally.', 'commands_completed':len(receipt['commands']),'completed':receipt['completed'],'binaries':receipt['binaries'],'files':{str(f.relative_to(rejected)):{'sha256':digest(f.read_bytes()),'bytes':f.stat().st_size} for f in sorted(rejected.rglob('*')) if f.is_file()}}
  raw=(json.dumps(summary,indent=2)+'\n').encode();(out/'rejected-campaign-summary.json').write_text(scrub(raw.decode()))
 manifest={'normalization':'work paths and user-home paths only; original/stored hashes are distinct when changed','files':files,'original_profiles':profiles,'public_profiles':'full merged samples and function/location tables preserved as pprof -raw text; original per-call protobufs remain compact local evidence'}
 (out/'preservation.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('Preserved',len(files),'text files and hashes for',len(profiles),'original profiles')

if __name__=='__main__':main()
