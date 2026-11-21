"""Extend the verified request/worker association of the previous timeline."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
w=Path(sys.argv[1]).resolve(); mode=sys.argv[2]
src=w/'worktree'; t=w/'temp'; dst=w/'evidence/published'; here=Path(__file__).resolve().parent

def get(spec):
    return subprocess.check_output(['git','show',spec],cwd=src)
previous='a81baaef944c69f67666277ae189422ef76d2c47:benchmarks/trigger-go-timeline/results-20261121/recipe/'
prior=t/'prior';prior.mkdir(exist_ok=True)
for name in ('overlay.py','timeline.go.txt','reader_test.go.txt','campaign.py'):
    (prior/name).write_bytes(get(previous+name))
subprocess.run([sys.executable,prior/'overlay.py',w],check=True)
if mode=='outer':
    raise SystemExit(0)
manifest=t/'overlay.json'
paths=json.loads(manifest.read_text())['Replace']
# Keep the same already-validated input/response/SQL correlation.
timeline=t/'harness/timeline/timeline.go'
s=timeline.read_text()
def change(old,new):
    global s
    assert s.count(old)==1,old
    s=s.replace(old,new)
change('type Row struct {','type Row struct {\n Inner Costs')
change('start = Now()','start = Now()\n r.Inner.start(start)')
change('r.TriggerNS += Now() - start','end:=Now();r.Inner.finish(end);r.TriggerNS += end - start')
timeline.write_text(s)
paths[str(timeline.with_name('inner.go'))]=str(here/'inner.go.txt')
bound=json.loads((here/'sites.json').read_text())
symbolmap=gzip.decompress(get('7c5893b3:benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'))
assert hashlib.sha256(symbolmap).hexdigest()=='1f8dcd20057090cde400f1439d0cc9d1c933b16490ba8ecd22269d909f1fe475'
symbols=dict(x.split(':',1) for x in symbolmap.decode().splitlines())
markers={}
for op in bound:
    if op['kind']=='mem' and mode!='detail':continue
    for idx,symbol in op['functions'].items():
        assert symbols[idx]==symbol and idx not in markers
        arg=',int64(uint32(l0))' if idx=='152' else ',0'
        expr=f'r.Inner.enterPhase({op["index"]})' if op['kind']=='phase' else f'r.Inner.enterMem({op["index"]}{arg})'
        markers[idx]='\n if r:=timeline.InnerRequest(unsafe.Pointer(m));r!=nil {defer r.Inner.leave('+expr+')}\n'
seen=set()
files={}
for p in sorted((src/'internal/generatedgo/code').rglob('*_pure.go')):
    orig=Path(paths.get(str(p),p)).read_text()
    def hook(m):
        idx=m[1]
        if idx not in markers:return m[0]
        assert idx not in seen;seen.add(idx)
        return m[0]+markers[idx]
    data=re.sub(r'(?m)^func Fn(\d+)\([^\n]+?\{',hook,orig)
    if data==orig:continue
    data=data.replace('r.Inner.leave(', 'r.Inner.Leave(').replace('r.Inner.enterPhase(', 'r.Inner.EnterPhase(').replace('r.Inner.enterMem(', 'r.Inner.EnterMem(')
    imp='"github.com/shibukawa/pgmem/bench/modelcase/timeline"'
    if imp not in data:data=data.replace('\nimport (','\nimport (\n'+imp,1)
    dest=t/'overlay'/('inner-'+p.name)
    dest.write_text(data);paths[str(p)]=str(dest)
    files[str(p.relative_to(src))]=hashlib.sha256(data.encode()).hexdigest()
assert seen==set(markers)
manifest.write_text(json.dumps({'Replace':paths}))
(dst/(mode+'-sites.json')).write_text(json.dumps(dict(files=files,indices=sorted(map(int,seen))),indent=2)+'\n')
