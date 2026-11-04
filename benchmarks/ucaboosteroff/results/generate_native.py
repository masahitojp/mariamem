import os,subprocess,json,time,sys
from pathlib import Path
w=Path(__file__).resolve().parents[1];s=w/'temp/source';t=w/'temp';e=w/'evidence'
assert json.loads((e/'build-exit.json').read_text())['exit_code']==0
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
sys.path.insert(0,str(s/'scripts'));import git_identity
git_identity.require_commit(s,'2b4a209f0f9d8864fbcc56e16efff8c54c36cad0')
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOTMPDIR=str(t/'go-tmp'),MARIAMEM_PHASE_TRACE=str(e/'native-phases.jsonl'),PYTHONPYCACHEPREFIX=str(t/'pycache'));env['MARIAMEM_EXPERIMENT_THREAD_BINDING']=str(e/'experimental-binding.json');env.pop('MARIAMEM_DEV_WORKSPACE',None)
cmd=[str(t/'venv/bin/python'),str(s/'scripts/regenerate_release_guest.py'),'--development','--guest-dir',str(t/'dev-guest'),'--output',str(t/'dev-native')]
(e/'native-command.json').write_text(json.dumps(cmd,indent=2)+'\n');start=time.time()
with (e/'native-generation.log').open('w') as f:p=subprocess.run(cmd,cwd=s,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
(e/'native-exit.json').write_text(json.dumps({'exit_code':p.returncode,'wall_seconds':time.time()-start})+'\n')
raise SystemExit(p.returncode)
