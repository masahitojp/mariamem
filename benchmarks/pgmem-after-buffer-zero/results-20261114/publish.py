from pathlib import Path
import json,hashlib,shutil
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';REPO=X.parents[2]
D=T/'product/benchmarks/pgmem-after-buffer-zero/results-20261114';D.mkdir(parents=True,exist_ok=False)
manifest={}
def save(src,dst):
 raw=src.read_bytes();text=raw.decode().replace(str(X),'<WORKSPACE>').replace(str(REPO),'<REPO>').replace(str(Path.home()),'<HOME>')
 text='\n'.join(line.rstrip() for line in text.split('\n'))
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(text)
 manifest[dst.relative_to(D).as_posix()]={'original_sha256':hashlib.sha256(raw).hexdigest(),'saved_sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
for f in E.iterdir():
 if f.is_file() and f.suffix in ('.json','.txt','.py','.csv'):save(f,D/f.name)
 if f.name=='console.log':save(f,D/'build-console.txt')
for f in (E/'runs').iterdir():save(f,D/'runs'/f.name)
for h in ('maria-suite','pg-suite','lifecycle'):
 for f in (T/h).rglob('*'):
  if f.is_file() and f.suffix in ('.go','.sql','.mod','.sum'):save(f,D/'harness'/h/f.relative_to(T/h))
for name in ('LICENSE','NOTICE'):save(T/'pgmem'/name,D/'harness'/('UPSTREAM-'+name+'.txt'))
(D/'publication.json').write_text(json.dumps({'recipe':'Replace workspace/repository/home paths with placeholders; strip trailing line whitespace; console.log saved as build-console.txt. Original input/execution hashes remain historical; use fresh receipts for a replay.','files':manifest},indent=2)+'\n')
print(D)
