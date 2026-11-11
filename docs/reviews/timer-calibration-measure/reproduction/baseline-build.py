from pathlib import Path
import os,subprocess,sys
W=Path(__file__).resolve().parents[1];B=W.parent/'timer-measure-baseline';S=B/'worktree';T=B/'temp'
env=dict(os.environ,MARIAMEM_DEV_WORKSPACE=str(B),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off')
for k in ('GOCACHE','GOPATH','GOMODCACHE'):env.pop(k,None)
python=str(W/'temp/venv/bin/python')
with (T/'build.log').open('w') as f:
 r=subprocess.run([python,str(S/'scripts/regenerate_release_guest.py'),'--development','--guest-dir',str(T/'guest'),'--output',str(T/'runtime')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT)
print('baseline host',r.returncode,flush=True)
if r.returncode:print((T/'build.log').read_text()[-6000:]);sys.exit(r.returncode)
env['PYTHONPATH']=str(T/'runtime/product/python')
subprocess.run([python,str(S/'tests/timer_runtime/oracle.py'),'--host',str(T/'runtime/mariamem-dev-host'),'--output',str(W/'evidence/baseline-oracle.json')],env=env,check=True,timeout=180)
