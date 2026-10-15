"""Guard externally; compile the isolated overlay, never canonical artifacts."""
import hashlib,json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[3];w=root.parent;t=w/'temp';e=w/'evidence';here=Path(__file__).resolve().parent
env=os.environ.copy();env.update(GOTOOLCHAIN='local',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOPATH=str(t/'gopath'),TMPDIR=str(t),GOTMPDIR=str(t))
go=env['GO_BIN']
identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=root))
identity['toolchain']=subprocess.check_output([go,'version'],text=True,env=env).strip()
identity['overlay']=json.loads((here/'instrumentation.json').read_text())
for name, item in identity['overlay'].items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==item['after'], name
identity['templates']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in here.iterdir() if p.is_file()}
(e/'build-input.json').write_text(json.dumps(identity,indent=2)+'\n')
for label,cmd in [('unit',[go,'test','-p','2','./internal/generatedgo/code/base','./internal/snapshot','-run','Test(D|E|MemFS|Prepared|Owned)','-count=1','-v']),('build',[go,'build','-p','2','-o',str(t/'d2-host'),'./cmd/mariamem-host'])]:
 print('START',label,flush=True)
 with (e/(label+'.txt')).open('w') as log:
  subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('PASS',label,flush=True)
identity['binary_sha256']=hashlib.sha256((t/'d2-host').read_bytes()).hexdigest()
(e/'build-input.json').write_text(json.dumps(identity,indent=2)+'\n')
