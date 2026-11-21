"""Build the single P1 harness, optionally with the Phase 3 counter overlay."""
import argparse
import json
import os
from pathlib import Path
import subprocess

p=argparse.ArgumentParser()
p.add_argument('workspace',type=Path)
p.add_argument('--counters',action='store_true')
a=p.parse_args()
root=a.workspace.resolve()
source=root/'worktree'; temp=root/'temp'; evidence=root/'evidence'
identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=source))
assert identity['source_commit']==json.loads((evidence/'phase1.json').read_bytes())['source_commit']
env=dict(os.environ,GOCACHE=str(temp/'analysis-cache'),GOTOOLCHAIN='local',GOWORK='off',GOMAXPROCS='8',CGO_ENABLED='0',GOFLAGS='',GOPROXY='off',TMPDIR=str(temp/'gotmp'))
(temp/'gotmp').mkdir(exist_ok=True)
args=['go','build','-trimpath','-p','1','-mod=readonly']
if a.counters:
    subprocess.run(['python3',Path(__file__).with_name('overlay.py'),source,temp/'harness',evidence/'functions.txt.gz',temp/'overlay'],check=True)
    args+=['-overlay',str(temp/'overlay/overlay.json')]
name='counter-probe' if a.counters else 'cpu-probe'
with (evidence/(name+'-build.log')).open('w') as out:
    subprocess.run(args+['-o',temp/name,'.'],env=env,cwd=temp/'harness',check=True,stdout=out,stderr=subprocess.STDOUT)
