"""Bounded campaign: boundaries, plain paired timing, separate resource runs."""
import argparse
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from experiment_disk import DiskGuard,run_guarded
p=argparse.ArgumentParser()
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();w=a.workspace.resolve();here=Path(__file__).resolve().parent
assert w/'worktree'==ROOT
venv=w/'temp/venv/bin/python';host=w/'temp/d-host'
env=dict(os.environ,TMPDIR=str(w/'temp/scratch'))
guard=DiskGuard(w,min_free_gib=16,budget_gib=12)
steps=[('boundaries-e',[str(here/'boundaries.py'),'--mode','e']),('boundaries-de',[str(here/'boundaries.py'),'--mode','de']),('plain',[str(here/'run.py'),'--repeats','5']),('resources',[str(here/'run.py'),'--repeats','3','--resources'])]
for name,arguments in steps:
 command=[str(venv),*arguments,'--host',str(host),'--output',str(w/'evidence'/name)]
 print('START',name,flush=True)
 with (w/'evidence'/(name+'.log')).open('w') as log:
  rc=run_guarded(command,guard,cwd=ROOT,env=env,output=log,timeout=300)
 if rc:raise SystemExit(f'{name} failed: {rc}')
 print('PASS',name,flush=True)
print('disk',guard.check(),flush=True)
