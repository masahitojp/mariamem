from pathlib import Path
import os,sys,subprocess,json
W=Path(__file__).resolve().parents[1]; S=W/'worktree'; T=W/'temp'; E=W/'evidence'
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit
from dev_guest import source_identity
source=source_identity(S)
require_commit(S,source['commit'])
assert source['commit']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()
env=dict(os.environ,MARIAMEM_DEV_WORKSPACE=str(W),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',MARIAMEM_PHASE_TRACE=str(T/'phases.jsonl'))
for key in ('GOCACHE','GOMODCACHE','GOPATH'): env.pop(key,None)
python=str(T/'venv/bin/python')
with (T/'build.log').open('w') as f:
    rc=subprocess.run([python,str(S/'scripts/regenerate_release_guest.py'),'--development','--guest-dir',str(T/'guest'),'--output',str(T/'runtime')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT).returncode
print('host regeneration exit',rc,flush=True)
if rc: print((T/'build.log').read_text()[-9000:]); sys.exit(rc)
env['PYTHONPATH']=str(T/'runtime/product/python')
with (T/'oracle.log').open('w') as f:
    rc=subprocess.run([python,str(S/'tests/timer_runtime/oracle.py'),'--host',str(T/'runtime/mariamem-dev-host'),'--output',str(E/'candidate-oracle.json')],cwd=S,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
print((T/'oracle.log').read_text()[-9000:])
sys.exit(rc)
