"""Bounded complete-suite measurement; standalone disk guard preserves failed pilots."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

W=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']).parent
T,E=W/'temp',W/'evidence'
S,P=T/'mariamem',T/'pgmem'
B=S/'benchmarks/lifecyclefull'
GO='/opt/homebrew/bin/go'
ENV=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'tmp'))
for name in ('go-tmp','tmp'): (T/name).mkdir(exist_ok=True)

def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
def write(name,value):(E/name).write_text(json.dumps(value,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identities():
 spec=importlib.util.spec_from_file_location('git_identity',S/'scripts/git_identity.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def build():
 plan=json.loads((B/'plan.json').read_text());m=identities()
 for repo in (S,P):assert not git(repo,'status','--porcelain'),repo
 m.require_commit(S,plan['source_commit']);h=git(S,'rev-parse','HEAD');m.require_commit(S,h)
 changed=git(S,'diff','--name-only',plan['source_commit'],h).splitlines();assert changed and all(x.startswith('benchmarks/lifecyclefull/') for x in changed),changed
 pin=m.ReleasePin(**plan['pgmem']);m.verify_release_pin(P,pin);assert git(P,'rev-parse','HEAD')==pin.source_commit
 assert subprocess.check_output([GO,'version'],env=ENV,text=True).strip()=='go version go1.27.3 darwin/arm64'
 inputs={'source_commit':plan['source_commit'],'harness_source_commit':h,'pgmem':plan['pgmem'],'platform':platform.platform(),
 'machine':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),
 'go':'go1.27.3','gomaxprocs':8,'guest_binding_sha256':sha(S/'internal/generatedgo/entry.go'),'plan':plan,'binaries':{}}
 write('preflight.json',inputs)
 for backend,target in [('mariamem','maria'),('pgmem','postgres')]:
  assert not (T/('bin-'+backend)).is_dir()
  command=[GO,'build','-trimpath','-buildvcs=true','-o',str(T/('bin-'+backend)),'./'+target]
  with (E/(backend+'-build.txt')).open('w') as f:subprocess.run(command,cwd=B,env=ENV,check=True,stdout=f,stderr=subprocess.STDOUT,timeout=900)
  stamp=m.verify_go_binary(S,T/backend,h,go=GO,toolchain='go1.27.3')
  inputs['binaries'][backend]={'sha256':sha(T/backend),'build_info':stamp}
  print('built',backend,flush=True)
 graph=subprocess.check_output([GO,'list','-m','-json','all'],cwd=B,env=ENV,text=True);(E/'module-graph.txt').write_text(graph)
 assert not git(S,'status','--porcelain') and not git(P,'status','--porcelain')
 write('inputs.json',inputs)

def validate(r,negative=False):
 assert r['cleanup'] and r['max_active']<=r['parallel']
 assert not r['scratch_remaining']
 if negative:assert not r['success'] and r['exit_code']==1 and 'pristine oracle' in r['error']
 else:
  assert r['success'] and r['exit_code']==0 and len(r['samples'])==r['count']
  assert all(s['oracle'] and s['cleanup'] and not s.get('error') for s in r['samples'])
  assert sorted(s['index'] for s in r['samples'])==list(range(r['count']))
 for s in r['samples']:
  assert s['end_ms']>=s['begin_ms']
  assert all(s['begin_ms']<=x['begin_ms']<=x['end_ms']<=s['end_ms'] for x in s['spans'])
  names=[x['name'] for x in s['spans']];assert len(set(names))==len(names)
  if not negative:assert {'start_or_fork','connect','select1','count_sum','update','verify_update','retire','close'}<=set(names)
  if not negative:assert ('seed' in names)==(r['mode']=='fresh')
 if not negative:
  version=next(s['version'] for s in r['samples'] if s['index']==0)
  assert ('12.3.3' in version) if r['backend']=='mariamem' else ('PostgreSQL 18.3' in version),version

def run(name,backend,mode,p,count=48,negative=False):
 assert not (E/(name+'.json')).exists(),name
 d=T/name;d.mkdir();scratch=d/'scratch';scratch.mkdir()
 cmd=[str(T/('bin-'+backend)),'--mode',mode,'--parallel',str(p),'--count',str(count),'--out',str(E/(name+'.json'))]
 if negative:cmd+=['--corrupt-seed']
 at=time.monotonic();proc=subprocess.run(cmd,cwd=B,env=dict(ENV,TMPDIR=str(scratch)),capture_output=True,text=True,timeout=190)
 external=(time.monotonic()-at)*1000
 (E/(name+'.stderr.txt')).write_text(proc.stderr)
 r=json.loads((E/(name+'.json')).read_text());r.update({'exit_code':proc.returncode,'external_process_ms':external,'scratch_remaining':sorted(x.name for x in scratch.iterdir())})
 write(name+'.json',r);validate(r,negative)
 print(name,round(r['suite_ms'],1),'ms', 'expected FAIL' if negative else 'PASS',flush=True)

cells=[('mariamem','fresh'),('pgmem','fresh'),('mariamem','fork'),('pgmem','fork')]
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','measure','all'],required=True);a=p.parse_args()
if a.phase in ('build','all'):build()
if a.phase in ('pilot','all'):
 for backend,mode in cells:
  run(f'pilot-{backend}-{mode}',backend,mode,1,2)
  run(f'negative-{backend}-{mode}',backend,mode,1,2,True)
 write('pilot-assessment.json',{'positive':4,'wrong_seed_detected':4,'cleanup':'PASS'})
if a.phase in ('measure','all'):
 assert json.loads((E/'pilot-assessment.json').read_text())['positive']==4
 for p in (1,4,8):
  for backend,mode in cells:run(f'warmup-{backend}-{mode}-p{p}',backend,mode,p)
 for repeat in range(3):
  for p in ([1,4,8] if repeat%2==0 else [8,4,1]):
   ordered=cells[repeat:]+cells[:repeat]
   for backend,mode in ordered:run(f'r{repeat}-{backend}-{mode}-p{p}',backend,mode,p)
 write('completion.json',{'primary_processes':36,'primary_cases':1728,'warmup_processes':12,'warmup_cases':576,'positive_pilot_processes':4,'positive_pilot_cases':8,'negative_processes':4,'negative_admitted_cases':4,'status':'OBSERVATION_COMPLETE'})
