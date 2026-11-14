from pathlib import Path
import subprocess,os
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';W=X/'worktree';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
for key in list(env):
 if key.startswith('MARIAMEM_BP_'):env.pop(key)
with (E/'source-check.log').open('w') as f:subprocess.run([str(T/'venv/bin/python'),'scripts/verify.py','check'],cwd=W,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800,check=True)
print('PASS canonical full source check',flush=True)
