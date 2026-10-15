"""Keep compact observations, not runtime files or generated build residue."""
import hashlib,json,sys
from pathlib import Path
here=Path(__file__).resolve().parent;root=here.parents[2];w=root.parent;e=w/'evidence'
out=root/'docs/reviews/d2-guest-evidence';out.mkdir(exist_ok=True)
def save(path,text):
 text=text.replace(str(w),'<workspace>')
 (out/path).parent.mkdir(parents=True,exist_ok=True)
 (out/path).write_text(text)
for name in ['summary.json','build-input.json','unit.txt','receiver-checks.json','overlay-replay.json','environment.json','first-unit-failure.txt','first-validator-observation.txt']:
 save(Path(name),(e/name).read_text())
for stage in ['pilot','audit','plain','resources']:
 ds=[{'label':p.parent.name,**json.loads(p.read_text())} for p in sorted((e/stage).glob('*/result.json'))]
 save(Path(stage)/'raw.json',json.dumps(ds,indent=2)+'\n')
 save(Path(stage)/'inputs.json',(e/stage/'inputs.json').read_text())
for stage in ['boundaries-e','boundaries-d2']:
 save(Path(stage)/'result.json',(e/stage/'result.json').read_text())
 records={p.name:json.loads(p.read_text()) for p in sorted((e/stage).glob('*-handoff.json'))}
 save(Path(stage)/'handoffs.json',json.dumps(records,indent=2)+'\n')
 for p in (e/stage).glob('*.log'):
  if p.stat().st_size:save(Path(stage)/(p.stem+'.txt'),p.read_text())
source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in here.iterdir() if p.is_file()}
save(Path('final-harness-sha256.json'),json.dumps(source,indent=2)+'\n')
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='checksums.json'}
(out/'checksums.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('retained',len(manifest),'files',sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),'bytes')
