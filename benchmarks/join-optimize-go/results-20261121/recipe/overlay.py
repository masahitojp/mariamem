"""Generate typed call-site probes only in selected optimizer functions on the pinned guest."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

w = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
src, temp, dst = w/'worktree', w/'temp', w/'evidence/published'
recipe = Path(__file__).resolve().parent
previous = 'a81baaef944c69f67666277ae189422ef76d2c47:benchmarks/trigger-go-timeline/results-20261121/recipe/'
def get(spec):
    return subprocess.check_output(['git','show',spec],cwd=src)
prior = temp/'prior'
prior.mkdir(exist_ok=True)
for filename in ('overlay.py','timeline.go.txt','reader_test.go.txt','campaign.py'):
    (prior/filename).write_bytes(get(previous+filename))
subprocess.run([sys.executable, prior/'overlay.py', w],check=True)
paths = json.loads((temp/'overlay.json').read_text())['Replace']
symbols = gzip.decompress(get('7c5893b3:benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'))
assert hashlib.sha256(symbols).hexdigest() == '1f8dcd20057090cde400f1439d0cc9d1c933b16490ba8ecd22269d909f1fe475'
names = dict(line.split(':',1) for line in symbols.decode().splitlines())
assert len(names)==21791 and names['14986']=='_ZN4JOIN8optimizeEv'
root='14986'
layers = {root:1,'15000':1,'14999':2,'15004':2,'15009':2,'15010':2,'12791':2,'15037':2,'14993':2}
level = {'parent':0,'branch':1,'deep':2,'focus':2}[mode]
focused = {('15000','15009'),('15000','15010'),('15009','12791'),('12791','12795')}
def selected(caller,target):
    return (caller,target) in focused if mode=='focus' else level>=layers[caller]
code = src/'internal/generatedgo/code'
sig = re.compile(r'^func Fn(\d+)\(([^)]*)\)([^\n{]*) \{',re.M)
signatures = {}
locations = {}
for path in sorted(code.rglob('*_pure.go')):
    original = path.read_text()
    for m in sig.finditer(original):
        i,args,returns = m.groups()
        assert i not in signatures
        signatures[i]=(args,returns.strip())
        if i in layers: locations[i]=path
assert set(locations)==set(layers)
imp='"github.com/shibukawa/pgmem/bench/modelcase/timeline"'
edges=[dict(id=0,caller='root',target=root,symbol=names[root],level=0)]
manifest={}
direct=re.compile(r'\bFn(\d+)\(')
indirect=re.compile(r'(m\.T0\[[^\]\n]+\]\.\(func\(([^)]*)\)([^)\n]*)\))\(')
for path in sorted(set(locations.values())):
    original=Path(paths.get(str(path),path)).read_text()
    data=original
    wrappers=[]
    for caller in sorted((i for i,p in locations.items() if p==path),key=int):
        start=data.index('func Fn'+caller+'(')
        start=data.index('{\n',start)+1
        end=data.index('\n}',start)
        body=data[start:end]
        cache={}
        def wrapper(target,args,ret,callback,line):
            key=target if not callback else 'indirect@'+str(line)
            if key in cache: return cache[key]
            idx=len(edges)
            name='timedJoinEdge'+str(idx)
            edges.append(dict(id=idx,caller=caller,target=key,symbol=names.get(target,key),level=layers[caller]))
            cache[key]=name
            if not selected(caller,target): return name
            call='target' if callback else 'Fn'+target
            params=', '.join(a.split()[0] for a in args.split(', '))
            action=('return ' if ret else '')+call+'('+params+')'
            extra='target '+callback+', ' if callback else ''
            wrappers.append('func '+name+'('+extra+args+') '+ret+' {\n if r:=timeline.JoinRequest(unsafe.Pointer(m),false); r!=nil { defer r.LeaveJoin(r.EnterJoin('+str(idx)+')) }; '+action+'\n}')
            return name
        def wrap_direct(m):
            j=m[1]
            a,r=signatures[j]
            name=wrapper(j,a,r,'',0)
            return name+'(' if selected(caller,j) else m[0]
        def wrap_indirect(m):
            expr,types,ret=m.groups()
            types=types.split(', ')
            assert types[0]=='*base.Module'
            args=', '.join(('m' if n==0 else 'a'+str(n))+' '+t for n,t in enumerate(types))
            callback='func('+', '.join(types)+')'+ret
            line=body.count('\n',0,m.start())
            name=wrapper('indirect',args,ret.strip(),callback,line)
            return name+'('+expr+', ' if selected(caller,'indirect') else m[0]
        assert body.count('m.T0[')==len(indirect.findall(body)),caller
        body=direct.sub(wrap_direct,body)
        body=indirect.sub(wrap_indirect,body)
        if caller==root:
            body='\n if r:=timeline.JoinRequest(unsafe.Pointer(m),true); r!=nil { defer r.LeaveJoin(r.EnterJoin(0)) }'+body
        data=data[:start]+body+data[end:]
    if data==original: continue
    if imp not in data:data=data.replace('\nimport (','\nimport (\n'+imp,1)
    data+='\n'+'\n'.join(wrappers)+'\n'
    dest=temp/'overlay'/('join-'+path.name)
    dest.write_text(data)
    paths[str(path)]=str(dest)
    manifest[str(path.relative_to(src))]=hashlib.sha256(data.encode()).hexdigest()
timeline=temp/'harness/timeline/timeline.go'
s=timeline.read_text()
assert s.count('type Row struct {')==1
timeline.write_text(s.replace('type Row struct {','type Row struct {\n Join JoinCosts\n joinActive,joinDepth int\n joinLast int64'))
inner=temp/'overlay/join.go'
inner.write_text((recipe/'join.go.txt').read_text().replace('SIZE',str(len(edges))))
paths[str(timeline.with_name('join.go'))]=str(inner)
(temp/'overlay.json').write_text(json.dumps({'Replace':paths}))
record=dict(parents={i:names[i] for i in layers},edges=edges)
edgefile=dst/'edges.json'
if edgefile.exists():assert json.loads(edgefile.read_bytes())==record
edgefile.write_text(json.dumps(record,indent=2)+'\n')
(dst/(mode+'-files.json')).write_text(json.dumps(manifest,indent=2)+'\n')
