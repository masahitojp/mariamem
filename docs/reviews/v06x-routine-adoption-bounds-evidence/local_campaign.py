import os
from pathlib import Path
import subprocess
import sys
p=Path(__file__).resolve().parents[1]
repo=p/'worktree'
env=dict(os.environ)
for key in ('GOCACHE','GOPATH','GOMODCACHE'):env.pop(key,None)
env['MARIAMEM_DEV_WORKSPACE']=str(p)
env['GOTOOLCHAIN']='go1.26.8'
def run(args,log):
    with (p/'evidence'/log).open('w') as stream:
        subprocess.run(args,cwd=repo,env=env,check=True,stdout=stream,stderr=subprocess.STDOUT)
run([sys.executable,'-m','venv',str(p/'temp/venv')],'venv.log')
python=str(p/'temp/venv/bin/python')
run([python,'-m','pip','install','pytest==8.4.2','PyMySQL==1.2.3'],'pip.log')
run(['gh','run','download','39379752111','-n','routine-guest-2c599bb904e3d523585347ccefc57ee1d833a993','-D',str(p/'temp/guest')],'download.log')
run([python,'scripts/git_identity.py','inspect','HEAD'],'source-identity.json')
run([python,'scripts/regenerate_release_guest.py','--development','--guest-dir',str(p/'temp/guest'),'--output',str(p/'temp/native')],'regeneration.log')
env['PYTHONPATH']=str(p/'temp/native/product/python')
run([python,str(p/'temp/definer_probe.py'),'--host',str(p/'temp/native/mariamem-dev-host'),'--output',str(p/'evidence/guest-definer.json')],'definer.log')
