from pathlib import Path
import subprocess,os,json,time
E=Path(__file__).resolve().parent;T=E.parent/'temp';W=Path('/private/tmp/mariamem-buffer-zero-audit-clone');assert json.loads((E/'canonical-check.json').read_text())['returncode']==0;assert json.loads((E/'validation-complete.json').read_text())['result']=='PASS';assert json.loads((E/'local-integration-disposition.json').read_text())['result'] in ('FULL_INTEGRATION_FAIL_ENVIRONMENT','ACCEPTED_KNOWN_EXTERNAL_CONNECTOR_DEFECT')
env=dict(os.environ,PATH=str(T/'venv/bin')+os.pathsep+os.environ['PATH'],GOTOOLCHAIN='go1.26.10',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),PWD=str(W),GOWORK='off',GOENV='off',GOFLAGS='')
identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=W,text=True));assert not subprocess.check_output(['git','status','--porcelain'],cwd=W)
cmd=[str(T/'venv/bin/python'),str(W/'benchmarks/forkcost/buffer-zero-candidate/ci_validate.py'),'--root',str(W),'--output',str(T/'ci-controls')];at=time.monotonic()
with (E/'ci-wrapper-check.log').open('w') as f:r=subprocess.run(cmd,cwd=W,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
(E/'ci-wrapper-check.json').write_text(json.dumps(dict(source=identity,returncode=r.returncode,seconds=time.monotonic()-at,go='go1.26.10',scope='Actual CI wrapper, unchanged data oracles; only module language directive lowered in scratch copy'),indent=2)+'\n')
if r.returncode:raise SystemExit(r.returncode)
print('PASS exact canonical CI controls wrapper on Go1.26.10',flush=True)
