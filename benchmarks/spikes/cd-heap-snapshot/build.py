"""Build only the isolated experiment; caller supplies disk/time guard."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];w=root.parent;t=w/'temp';e=w/'evidence';here=Path(__file__).resolve().parent
for p in [t,e]:p.mkdir(exist_ok=True)
env=os.environ.copy();env.update(GOTOOLCHAIN='local',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOPATH=str(t/'gopath'),TMPDIR=str(t),GOTMPDIR=str(t),PYTHONPYCACHEPREFIX=str(t/'pycache'))
go=env['GO_BIN'];identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=root));identity['toolchain']=subprocess.check_output([go,'version'],env=env,text=True).strip();identity['overlay']=json.loads((here/'instrumentation.json').read_text())
for n,d in identity['overlay'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==d['after'],n
identity['sources']={str(p.relative_to(here)):hashlib.sha256(p.read_bytes()).hexdigest() for p in here.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(e/'build-input.json').write_text(json.dumps(identity,indent=2)+'\n')
commands=[('unit',[go,'test','-p','2','./internal/generatedgo/code/base','./internal/snapshot','-run','Test(CFile|Heap|DBlock|DIntegration|MemFS|Prepared|Owned)','-count=1','-v'])]
if '--unit' not in sys.argv:commands.append(('build',[go,'build','-p','2','-o',str(t/'heap-spike'),'./benchmarks/spikes/cd-heap-snapshot/runner']))
for label,cmd in commands:
 print('START',label,flush=True)
 with (e/(label+'.txt')).open('w') as log:subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('PASS',label,flush=True)
if '--unit' not in sys.argv:identity['binary_sha256']=hashlib.sha256((t/'heap-spike').read_bytes()).hexdigest()
(e/'build-input.json').write_text(json.dumps(identity,indent=2)+'\n')
