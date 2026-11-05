"""Preserve compact public evidence; originals stay in owned evidence."""
from pathlib import Path
import hashlib,json,shutil
w=Path('.').resolve(); repo=w/'worktree'; out=repo/'benchmarks/spikes/issue65-go-wire'; ev=out/'evidence';ev.mkdir(exist_ok=True)
for p in (w/'temp/tools').iterdir():
 if p.is_file():shutil.copy2(p,out/p.name)
rows=[]
for p in (w/'evidence').rglob('*'):
 if not p.is_file() or p.name in ('default-cleanup-audit.json',):continue
 rel=p.relative_to(w/'evidence');data=p.read_bytes()
 if p.name.startswith('guest-build'):
  content=data.decode(); marker=content.find('\n{\n'); content=content if marker<0 else content[:marker]+'\n[receipt inventory omitted here; guest records retained separately]\n'; target=ev/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content.replace(str(w),'/exp').replace(str(w.parents[2]),'<repository>'));rows.append({'path':str(rel),'original_sha256':hashlib.sha256(data).hexdigest(),'saved_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'transformation':'personal paths normalized; repeated receipt inventory omitted'});continue
 try:content=data.decode()
 except UnicodeDecodeError:continue
 content=content.replace(str(w),'/exp').replace(str(w.parents[2]),'<repository>')
 target=ev/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
 rows.append({'path':str(rel),'original_sha256':hashlib.sha256(data).hexdigest(),'saved_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(ev/'preservation.json').write_text(json.dumps(rows,indent=2)+'\n')
shutil.copy2(w/'temp/artifact/guest.json',ev/'guest-final.json')
shutil.copy2(repo/'guest/experimental.patch',ev/'experimental.patch')
print('Preserved',len(rows),'evidence files and prototype sources')
