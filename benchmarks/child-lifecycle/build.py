#!/usr/bin/env python3
"""Build clean pinned local clones; worktree stamp omission is rejected."""
import argparse
import hashlib
import shutil
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from git_identity import require_commit

def main():
 p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('--go',required=True);a=p.parse_args()
 work=a.workspace.resolve();temp=work/'temp';evidence=work/'evidence';temp.mkdir(parents=True,exist_ok=True);evidence.mkdir(parents=True,exist_ok=True);(temp/'go-tmp').mkdir(exist_ok=True)
 go=Path(a.go).resolve()
 assert subprocess.check_output([str(go),'version'],text=True).startswith('go version go1.26.8 ')
 if not (temp/'go').exists():(temp/'go').symlink_to(go)
 env=dict(os.environ,GOTOOLCHAIN='local',GOPATH=os.environ.get('GOPATH',str(temp/'go-path')),GOCACHE=str(temp/'go-cache'),GOTMPDIR=str(temp/'go-tmp'),CGO_ENABLED='0')
 inputs={'control':(str(temp/'control-clone'),'9cedaa76720336ec8304b9db7f28d6b1174b13b6'),'observed':(str(temp/'observed-clone'),'0a36f304b5b4c940f15359ce9e35a97db9512869')};records=[]
 for variant,(directory,commit) in inputs.items():
  root=Path(directory);assert not root.exists()
  subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT),str(root)],check=True)
  subprocess.run(['git','-C',str(root),'checkout','--detach',commit],check=True)
  assert (root/'.git').is_dir();require_commit(root,commit)
  assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==commit
  assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain'])
  for kind,package in [('child','./benchmarks/child-lifecycle'),('host','./cmd/mariamem-host')]:
   binary=temp/f'{variant}-{kind}';cmd=[str(go),'build','-buildvcs=true','-p','2','-o',str(binary),package];at=time.monotonic()
   with (evidence/f'build-{variant}-{kind}.txt').open('w') as log:subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
   stamp=subprocess.check_output([str(go),'version','-m',str(binary)],text=True)
   assert 'vcs.revision='+commit in stamp and 'vcs.modified=false' in stamp,(variant,kind,stamp)
   records.append(dict(variant=variant,kind=kind,source_commit=commit,argv=cmd,elapsed_seconds=time.monotonic()-at,sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),stamp=stamp))
   (evidence/'builds.json').write_text(json.dumps(records,indent=2)+'\n')
 print('PASS: four clean exact-commit binary stamps')
if __name__=='__main__':main()
