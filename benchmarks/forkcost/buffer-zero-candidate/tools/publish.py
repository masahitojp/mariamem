from pathlib import Path
import json,hashlib,gzip,shutil,subprocess
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp';D=W/'benchmarks/forkcost/buffer-zero-candidate';D.mkdir(parents=True,exist_ok=True);rows=[]
def add(src,name,compressed=False,normalize=True):
 raw=src.read_bytes();data=raw
 if normalize:
  try:
   text=raw.decode()
   for a,b in ((str(X),'<workspace>'),(str(W),'<repo>'),(str(Path.home()),'<home>')):text=text.replace(a,b)
   text='\n'.join(line.rstrip() for line in text.splitlines())+('\n' if text.endswith('\n') else '')
   data=text.encode()
  except UnicodeDecodeError:pass
 name=name.removesuffix('.gz') if compressed else name
 name=name[:-4]+'.txt' if name.endswith('.log') else name
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(data)
 rows.append(dict(source=str(src.relative_to(X)),target=name,raw_sha256=hashlib.sha256(raw).hexdigest(),public_uncompressed_sha256=hashlib.sha256(data).hexdigest(),compressed=False))
for src in sorted((E/'harness').rglob('*')):
 if src.is_file():add(src,'harness/'+str(src.relative_to(E/'harness')))
for p in (D/'harness').glob('*/go.mod'):
 s=p.read_text();p.write_text(s[:s.index('replace github.com/masahitojp/mariamem')]+ 'replace github.com/masahitojp/mariamem => ../../../../..\n')
for n in ('runs',):
 for src in sorted((E/n).iterdir()):add(src,n+'/'+src.name)
for src in sorted(E.glob('*.py')):
 if src.name=='ci_validate.py':add(src,'ci_validate.py')
 else:add(src,'tools/'+src.name)
for src in sorted(E.glob('*')):
 if not src.is_file() or src.suffix not in ('.json','.csv','.txt','.log','.jsonl'):continue
 if src.name=='previous-canonical-build.json':add(src,'build-evidence/'+src.name,normalize=False)
 elif src.name in ('guest-build.log','guest-phases.jsonl','native-build.log','native-phases.jsonl'):
  add(src,'build-evidence/'+src.name+'.gz',compressed=True)
 else:add(src,('evidence/' if src.suffix in ('.json','.csv') else 'validation/')+src.name)
for src in (T/'guest/guest.json',T/'native/development.json',T/'native/installation-inputs.json',T/'native/translation/input-manifest.json',T/'build/buffer-pool-contract-0.json'):
 add(src,'build-evidence/'+src.parent.name+'-'+src.name+'.gz',compressed=True)
(D/'publication.json').write_text(json.dumps({'normalization':'Paths and trailing whitespace only; numerical observations unchanged. Portable harness replace path follows repository location. Historical input records are evidence, not current install inputs.','files':rows},indent=2)+'\n')
print('Published',len(rows),'compact evidence files')
