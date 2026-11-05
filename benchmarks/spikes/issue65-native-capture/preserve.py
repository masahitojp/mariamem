"""Preserve spike source and compact observations; keep raw hashes separately."""
from pathlib import Path
import hashlib,json,shutil
w=Path('.').resolve();r=w/'worktree';out=r/'benchmarks/spikes/issue65-native-capture';ev=out/'evidence';ev.mkdir(exist_ok=True)
for p in (w/'temp/tools').iterdir():
 if p.is_file():shutil.copy2(p,out/p.name)
rows=[]
for p in (w/'evidence').rglob('*'):
 if not p.is_file() or p.name.startswith(('default-cleanup-audit','cleanup-','staged-diff-check')):continue
 rel=p.relative_to(w/'evidence');raw=p.read_bytes()
 try:content=raw.decode()
 except UnicodeDecodeError:continue
 transformation='personal paths normalized'
 if p.name.startswith('guest-build'):
  marker=content.find('\n{\n')
  if marker>=0:content=content[:marker]+'\n[Repeated receipt inventory omitted; full guest records saved separately]\n';transformation+='; repeated receipt inventory omitted'
 if rel.parts[0]=='compile-flags':
  content='\n'.join(line.rstrip() for line in content.splitlines()).rstrip()+'\n';transformation+='; compile-log trailing whitespace/blank EOF normalized'
 content=content.replace(str(w),'/exp').replace(str(w.parents[2]),'<repository>')
 target=ev/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
 rows.append({'path':str(rel),'original_sha256':hashlib.sha256(raw).hexdigest(),'saved_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'transformation':transformation})
(ev/'preservation.json').write_text(json.dumps(rows,indent=2)+'\n');print('Preserved',len(rows),'observations and prototype tools')
