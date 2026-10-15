"""Preserve compact evidence and exact source identities, not build residue."""
import hashlib,json
from pathlib import Path
here=Path(__file__).resolve().parent;root=here.parents[2];w=root.parent;e=w/'evidence';out=root/'docs/reviews/go-heap-snapshot-evidence';out.mkdir(exist_ok=True)
def save(name,text):
 (out/name).parent.mkdir(parents=True,exist_ok=True)
 (out/name).write_text(text.replace(str(w),'<workspace>'))
for name in ['summary.json','unit.txt','unit-race.txt','build-input.json','overlay-replay.json','environment.json']:save(name,(e/name).read_text())
for stage in ['pilot','audit','boundaries','plain','resources']:
 cases=[dict(label=p.stem,**json.loads(p.read_text())) for p in sorted((e/stage).glob('n*.json'))]
 save(stage+'.json',json.dumps(cases,indent=2)+'\n');save(stage+'-inputs.json',(e/stage/'inputs.json').read_text())
if (e/'initial').exists():
 for name in ['summary.json','build-input.json']:save('initial/'+name,(e/'initial'/name).read_text())
 for stage in ['plain','resources']:
  cases=[dict(label=p.stem,**json.loads(p.read_text())) for p in sorted((e/'initial'/stage).glob('n*.json'))]
  save('initial/'+stage+'.json',json.dumps(cases,indent=2)+'\n')
sources={str(p.relative_to(here)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(here.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
save('final-source-sha256.json',json.dumps(sources,indent=2)+'\n')
checks={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='checksums.json'}
save('checksums.json',json.dumps(checks,indent=2)+'\n');print('retained',len(checks),'files')
