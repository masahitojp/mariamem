from pathlib import Path
import subprocess,os,json,hashlib
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp';B=Path('/private/tmp/mariamem-buffer-zero-audit-clone');env=dict(os.environ,GOTOOLCHAIN='go1.26.10',PWD=str(B),GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=W)
identity=subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=B,text=True);(E/'audit-source.json').write_text(identity)
with (E/'license-audit.log').open('w') as f:
 subprocess.run(['go','build','-p','1','-trimpath','-buildvcs=true','-o',str(T/'attribution-host'),'./cmd/mariamem-host'],cwd=B,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
 subprocess.run([str(T/'venv/bin/python'),'scripts/audit_generated_licenses.py','--linked',str(T/'guest/linked.wasm'),'--guest',str(T/'guest/mariamem.wasm'),'--function-map',str(E/'function-map.txt'),'--host',str(T/'attribution-host'),'--output',str(E/'generated-license-evidence.json')],cwd=W,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=W)
raw=(E/'generated-license-evidence.json').read_bytes();(W/'release/generated-license-evidence.json').write_bytes(raw)
p=W/'release/distribution-licenses.json';v=json.loads(p.read_text());v['evidence_sha256']=hashlib.sha256(raw).hexdigest();p.write_text(json.dumps(v,indent=2)+'\n')
print('PASS fresh retained-symbol audit for candidate clean-source host',flush=True)
