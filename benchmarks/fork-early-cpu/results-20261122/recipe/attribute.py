"""Count sample stacks once per named path and pair recorded calls per Fork."""
from pathlib import Path
import csv,gzip,json,re,statistics
w=Path.cwd(); e=w/'evidence'; t=w/'temp'
src=(t/'cpu-early-raw.txt').read_text().splitlines()
locations={}
current=None
for line in src[src.index('Locations'):]:
    hit=re.match(r'\s*(\d+): 0x[0-9a-f]+ M=\d+ (\S+)',line)
    if hit:current=int(hit[1]);locations[current]=[hit[2]]
    elif line.startswith('             ') and current is not None:
        locations[current].append(line.split()[0])
wanted={'from_text':'Fn20147','charset_lookup':'Fn975','registry_init':'Fn966','uca_init':'Fn468','grow':'MemoryGrow'}
stacks=[]
for l in src[:src.index('Locations')]:
    hit=re.match(r'\s*(\d+)\s+\d+:\s+([0-9 ]+)\s*$',l)
    if hit:
        ids=map(int,hit[2].split())
        frames={f.rsplit('.',1)[-1] for k in ids for f in locations[k]}
        stacks.append((int(hit[1]),frames))
assert sum(n for n,_ in stacks)>0
print('early sample count',sum(n for n,_ in stacks))
for k,v in wanted.items():
    print(k,sum(n for n,f in stacks if v in f),'under from_text',sum(n for n,f in stacks if v in f and 'Fn20147' in f))
wall=[]
for f in sorted((e/'runs').glob('detail-*.json.gz')):
    data=json.loads(gzip.decompress(f.read_bytes()))
    starts=[x for x in data.values() if x.get('operation')=='startup']
    assert len(starts)==22
    # Ordered timing files distinguish the initial server from the 21 clones.
    launches=sorted((int(k[:-5].rsplit('-',1)[1]),x) for k,x in data.items() if x.get('operation')=='startup')
    for _,x in launches[1:]:
        ev=x['phase']
        ms={r['name']:r['start_ns'] for r in ev if r.get('name')}
        a,b=ms['embedded_begin'],ms['embedded_options_complete']
        hit=[r for r in ev if r['id']==20147 and a<=r['start_ns']<=r['end_ns']<=b]
        assert len(hit)==1
        z=hit[0]
        lookup=[r for r in ev if r['id']==975 and z['start_ns']<=r['start_ns']<=r['end_ns']<=z['end_ns']]
        assert len(lookup)==5
        dur=z['end_ns']-z['start_ns']
        first=sorted(lookup,key=lambda x:x['start_ns'])[0]
        ns=sum(r['end_ns']-r['start_ns'] for r in lookup)
        wall.append(dict(block=f.stem.split('-')[1].split('.')[0],from_text_ms=dur/1e6,lookup_ms=ns/1e6,first_lookup_ms=(first['end_ns']-first['start_ns'])/1e6,other_ms=(dur-ns)/1e6,early_ms=(b-a)/1e6))
assert len(wall)==84
with (e/'collations.csv').open('w') as f:
    wr=csv.DictWriter(f,fieldnames=wall[0],lineterminator='\n');wr.writeheader();wr.writerows(wall)
for k in wall[0]:
    if k!='block':
        v=[r[k] for r in wall]
        print(k,statistics.median(v),min(v),max(v),[round(statistics.median(v[i:i+21]),4) for i in range(0,84,21)])
