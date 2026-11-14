from pathlib import Path
import os,subprocess,json,time
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';W=Path('/private/tmp/mariamem-buffer-zero-audit-clone');env=dict(os.environ,PWD=str(W),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'),PYTHONDONTWRITEBYTECODE='1',MARIAMEM_PHASE_TRACE=str(E/'canonical-check-phases.jsonl'))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=W)
source=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=W,text=True));(E/'canonical-check-source.json').write_text(json.dumps(source,indent=2)+'\n')
for stage in ('check','integration'):
 cmd=[str(T/'venv/bin/python'),'scripts/verify.py',stage];at=time.monotonic()
 with (E/('canonical-'+stage+'.log')).open('w') as f:r=subprocess.run(cmd,cwd=W,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=2400)
 (E/('canonical-'+stage+'.json')).write_text(json.dumps(dict(source=source,argv=cmd,returncode=r.returncode,seconds=time.monotonic()-at,platform='darwin-arm64',go='go1.26.10'),indent=2)+'\n')
 print(stage,'returncode',r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=W)
print('PASS clean canonical check and integration',flush=True)
