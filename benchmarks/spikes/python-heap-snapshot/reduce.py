import hashlib,json
from pathlib import Path
h=Path(__file__).resolve().parent;root=h.parents[2];w=root.parent;e=w/'evidence';out=root/'docs/reviews/python-heap-snapshot-evidence';out.mkdir(exist_ok=True)
def save(n,s):
 p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s.replace(str(w),'<workspace>'))
for n in ['source-identity.json','build-input.json','environment.json','python-packages.txt','pgmem-inputs.json','summary.json','unit.txt','host.txt','broker.txt','overlay-replay.json','checks.json']:save(n,(e/n).read_text())
for stage in ['pilot','plain','resources']:
 cases=[dict(label=p.parent.name,**json.loads(p.read_text())) for p in sorted((e/stage).glob('n*/result.json'))]
 save(stage+'.json',json.dumps(cases,indent=2)+'\n');save(stage+'-inputs.json',(e/stage/'inputs.json').read_text())
for p in sorted((e/'verify').iterdir()):save('verify/'+p.name,p.read_text())
sources={str(p.relative_to(h)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(h.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
save('final-source-sha256.json',json.dumps(sources,indent=2)+'\n')
checks={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='checksums.json'};save('checksums.json',json.dumps(checks,indent=2)+'\n');print('retained',len(checks),'files')
