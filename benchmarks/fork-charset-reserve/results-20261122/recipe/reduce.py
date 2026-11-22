from pathlib import Path
import csv,gzip,json,statistics as stat
out=Path('evidence')
runs=[];forks=[];pairs=[];dp=[]
def write(name,data):
    with (out/(name+'.csv')).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=data[0],lineterminator='\n')
        writer.writeheader();writer.writerows(data)
for p in sorted((out/'runs').glob('*.json.gz')):
    d=json.loads(gzip.decompress(p.read_bytes()))
    meta=d.pop('measurement');trace=d.pop('suite.json')
    names=('fork','sample')
    sums={name:sum(s['end_ms']-s['start_ms'] for s in trace['spans'] if s['kind']==name) for name in names}
    trial=dict(meta,suite_ms=trace['elapsed_ms'],forks_ms=sums['fork'],sample_ms=sums['sample'])
    runs.append(trial)
    if meta['mode']!='diag':continue
    starts=sorted((int(name[:-5].rsplit('-',1)[1]),x) for name,x in d.items() if x.get('operation')=='startup')
    assert len(starts)==22
    this=[]
    for i,(_,data) in enumerate(starts[1:],1):
        events=data['phase'];r=[e for e in events if e['id']==966]
        assert len(r)==1
        a,b=r[0]['start_ns'],r[0]['end_ns']
        within=[e for e in events if a<=e['start_ns']<=e['end_ns']<=b]
        assert sum(e['id']==809 for e in within)==2
        entries=lambda fn:[e for e in within if e['id']==fn]
        def dur(fn):return sum(e['end_ns']-e['start_ns'] for e in entries(fn))/1e6
        row=dict(block=meta['block'],arm=meta['arm'],fork=i,registry_ms=(b-a)/1e6,
            realloc_calls=len(entries(987)),realloc_ms=dur(987),alloc_dynamic_calls=len(entries(795)),hash_init_ms=dur(809),collations_count=len(entries(963)),collations_ms=dur(963))
        this.append(row);forks.append(row)
    trial['registry_ms']=stat.median(r['registry_ms'] for r in this)
    trial['realloc_calls']=stat.median(r['realloc_calls'] for r in this)
for b in range(1,7):
    rows=[r for r in runs if r['block']==b and r['mode']=='perf']
    order=sorted(rows,key=lambda x:x['position'])
    assert len(order)==3 and order[0]['arm']==order[2]['arm']!=order[1]['arm']
    row=dict(block=b,repeated=order[0]['arm'])
    for k in ('suite_ms','forks_ms','sample_ms','rss_bytes'):
        a,c=[stat.mean(r[k] for r in rows if r['arm']==arm) for arm in ('control','reserve')]
        row.update({k+'_control':a,k+'_reserve':c,k+'_saved':a-c,k+'_noise':abs(order[0][k]-order[2][k])})
    pairs.append(row)
for b in range(1,5):
    a,c=[next(r for r in runs if r['mode']=='diag' and r['block']==b and r['arm']==arm) for arm in ('control','reserve')]
    dp.append(dict(block=b,registry_control_ms=a['registry_ms'],registry_reserve_ms=c['registry_ms'],registry_saved_ms=a['registry_ms']-c['registry_ms'],realloc_control=a['realloc_calls'],realloc_reserve=c['realloc_calls']))
assert len(runs)==28 and len(forks)==168
write('pairs',pairs);write('registration-by-fork',forks);write('registration-pairs',dp)
for k in pairs[0]:
    if k not in ('block','repeated'):
        v=[r[k] for r in pairs];print(k,round(stat.median(v),5),min(v),max(v))
for k in dp[0]:
    if k!='block':
        v=[r[k] for r in dp];print(k,round(stat.median(v),6),min(v),max(v))
