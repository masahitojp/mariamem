#!/usr/bin/env python3
"""Finite native attribution campaign; no builds or correctness changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]

def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
 work=a.workspace.resolve();out=work/'evidence'/'campaign';out.mkdir(parents=True,exist_ok=False)
 temp=work/'temp';commands=[];begin=time.monotonic()
 binaries={v:{kind:temp/f'{v}-{kind}' for kind in ('child','host')} for v in ('control','observed')}
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 receipt={'platform':platform.platform(),'machine':platform.machine(),'python':sys.version,'binaries':{v:{k:{'sha256':sha(path),'stamp':subprocess.check_output([str(temp/'go'),'version','-m',str(path)],text=True)} for k,path in bs.items()} for v,bs in binaries.items()},'commands':commands,'completed':False}
 def save(): (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 def run(name,cmd,observed=False):
  assert time.monotonic()-begin<1800,'campaign time budget'
  scratch=temp/'scratch'/name;scratch.mkdir(parents=True)
  env=dict(os.environ,TMPDIR=str(scratch));env.pop('MARIAMEM_TIMING_DIR',None)
  if observed:
   traces=out/(name+'-traces');traces.mkdir();env['MARIAMEM_TIMING_DIR']=str(traces)
  start=time.monotonic()
  with (out/(name+'.txt')).open('w') as log:
   r=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
  commands.append({'name':name,'argv':list(map(str,cmd)),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'timing_enabled':observed})
  save();assert r.returncode==0,name
  assert not list(scratch.iterdir()),(name,'scratch remains')
 cases=[('light',0,1),('medium',10,1),('large',100,1),('parallel',10,4)]
 for case,size,workers in cases:
  for trial in range(3):
   variants=('control','observed') if trial%2==0 else ('observed','control')
   for variant in variants:
    name=f'go-{case}-{trial}-{variant}'
    cmd=[binaries[variant]['child'],'--payload-mib',size,'--tables',1 if size==0 else 8,'--forks',4,'--workers',workers,'--workload','app-connections','--label',variant,'--out',out/(name+'.json')]
    run(name,cmd,variant=='observed')
 for scale,n in [('small',3),('medium',3),('100mib',1)]:
  for trial in range(n):
   for variant in (('control','observed') if trial%2==0 else ('observed','control')):
    name=f'python-{scale}-{trial}-{variant}'
    run(name,[sys.executable,ROOT/'benchmarks/sharedhost/workflow.py','--sdk',ROOT/'python','--host',binaries[variant]['host'],'--scale',scale,'--output',out/(name+'.json')],variant=='observed')
 for phase in ['fork','close']:
  name='profile-'+phase;profiles=out/name
  run(name,[binaries['observed']['child'],'--payload-mib',0,'--forks',24,'--workload','app-connections','--label','profile-only','--profile-dir',profiles,'--profile-phase',phase,'--out',out/(name+'.json')],True)
  paths=sorted(profiles.glob('*.pprof'));assert len(paths)==24
  for kind,args in [('flat',['-top']),('cum',['-top','-cum'])]:
   text=subprocess.check_output([str(temp/'go'),'tool','pprof',*args,'-nodecount=50',str(binaries['observed']['child']),*map(str,paths)],text=True,stderr=subprocess.STDOUT)
   (out/(name+'-'+kind+'.txt')).write_text(text)
 assert len(commands)==40
 for v,bs in binaries.items():
  for k,path in bs.items():assert sha(path)==receipt['binaries'][v][k]['sha256']
 receipt['completed']=True;receipt['elapsed_seconds']=time.monotonic()-begin;save()
 print('PASS: 24 Go paired cells, 14 Python paired cells, 2 diagnostic profile cells')

if __name__=='__main__':main()
