from pathlib import Path
import subprocess,os,json,hashlib
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
for cmd in [[os.sys.executable,str(E/'build-harness.py'),'spike'],[os.sys.executable,str(E/'build-extra.py'),'spike']]:
 with (E/('spike-harness-build.log' if 'build-harness.py' in cmd[1] else 'spike-extra-build.log')).open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
print('PASS experiment harness binaries',flush=True)
