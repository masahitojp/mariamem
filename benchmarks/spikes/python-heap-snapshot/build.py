import hashlib,json,os,subprocess
from pathlib import Path
h=Path(__file__).resolve().parent;root=h.parents[2];w=root.parent;t=w/'temp';e=w/'evidence'
env=os.environ.copy();env.update(GOTOOLCHAIN='local',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOPATH=str(t/'gopath'),TMPDIR=str(t),GOTMPDIR=str(t))
go=env['GO_BIN'];record=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=root));record['toolchain']=subprocess.check_output([go,'version'],text=True).strip();record['overlay']=json.loads((h/'instrumentation.json').read_text())
for n,d in record['overlay'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==d['after'],n
record['source_hashes']={str(p.relative_to(h)):hashlib.sha256(p.read_bytes()).hexdigest() for p in h.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(e/'build-input.json').write_text(json.dumps(record,indent=2)+'\n')
for label,cmd in [('unit',[go,'test','-p','2','./internal/generatedgo/code/base','./internal/snapshot','-run','Test(Heap|DBlock|DIntegration|MemFS|Prepared|Owned)','-count=1','-v']),('host',[go,'build','-p','2','-o',str(t/'mariamem-host'),'./cmd/mariamem-host']),('broker',[go,'build','-p','2','-o',str(t/'broker'),'./benchmarks/spikes/python-heap-snapshot/broker'])]:
 print('START',label,flush=True)
 with (e/(label+'.txt')).open('w') as f:subprocess.run(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 print('PASS',label,flush=True)
record['binaries']={n:hashlib.sha256((t/n).read_bytes()).hexdigest() for n in ['mariamem-host','broker']};(e/'build-input.json').write_text(json.dumps(record,indent=2)+'\n')
