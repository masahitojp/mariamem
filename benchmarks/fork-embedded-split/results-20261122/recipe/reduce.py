from collections import Counter
from pathlib import Path
import csv,gzip,json,statistics as stat
out=Path('evidence')
scopes=json.loads((out/'functions.json').read_text())
suites=[];rows=[];calls=[]
def table(name,data):
    with (out/(name+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=data[0],lineterminator='\n')
        w.writeheader();w.writerows(data)
def ticks(data):
    return {x['name']:x['offset_ns'] for x in data['events']}
def merge(intervals):
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]:
            prev=merged.pop()
            merged.append((prev[0],max(end,prev[1])))
        else:
            merged.append((start,end))
    return merged
def duration(intervals):
    return sum(b-a for a,b in merge(intervals))/1e6
markers_expected=None
for f in sorted((out/'runs').glob('*.json.gz')):
    arm,block=f.name.split('.')[0].split('-')
    data=json.loads(gzip.decompress(f.read_bytes()))
    suite=data.pop('suite.json')
    fork_spans=[s['end_ms']-s['start_ms'] for s in suite['spans'] if s['kind']=='fork']
    suites.append(dict(arm=arm,block=block,suite_ms=suite['elapsed_ms'],fork_sum_ms=sum(fork_spans)))
    if arm=='normal':continue
    owner=None;previous=-1;i=0
    for name,event in sorted(data.items(),key=lambda item:int(item[0][:-5].rsplit('-',1)[1])):
        seq=int(name[:-5].rsplit('-',1)[1])
        if event['operation']=='startup':owner=(seq,event)
        if event['operation']!='fork':continue
        assert owner and previous<owner[0]<seq
        previous=seq;i+=1
        obs=owner[1]
        if arm=='host':
            assert not obs.get('phase') and not obs.get('guest')
            continue
        events=obs['phase']
        guest=ticks(obs['guest'])
        assert all(0<=e['start_ns']<=e['end_ns'] for e in events)
        spans={int(k):[(e['start_ns'],e['end_ns']) for e in events if e['id']==int(k)] for k in scopes}
        assert len(spans[5583])==1 and len(spans[5749])==2
        assert len(spans[5434])==len(spans[18602])==1
        assert abs(duration(spans[5749])-(guest['server_init_complete']-guest['server_init_begin'])/1e6)<0.25
        lo,hi=spans[5583][0]
        def embedded(seq):
            return [(a,b) for a,b in seq if lo<=a<=b<=hi]
        assert len(embedded(spans[5434]))==len(embedded(spans[18602]))==1
        engine=spans[5434]+spans[18602]
        assert duration(engine)==(sum(b-a for a,b in engine)/1e6)
        markers=sorted((e['start_ns'],e['name']) for e in events if e.get('name') and lo<=e['start_ns']<=hi)
        key=[name for _,name in markers];assert len(key)==len(set(key))>=7
        if markers_expected is None:markers_expected=key
        assert key==markers_expected,(key,markers_expected)
        row=dict(block=block,fork=i,server_ms=duration(spans[5749]),embedded_ms=duration(spans[5583]),innodb_ms=duration(spans[18602]),aria_ms=duration(spans[5434]),embedded_outside_engines_ms=(hi-lo)/1e6-duration(engine))
        points=[(lo,'embedded.entry'),*markers,(hi,'embedded.return')]
        for (a,name),(b,next_name) in zip(points,points[1:]):
            key=name+' → '+next_name
            row[key]=(b-a)/1e6
            row[key+' excl InnoDB+Aria']=(b-a)/1e6-duration([(max(a,x),min(b,y)) for x,y in engine if max(a,x)<min(b,y)])
        boundaries={name:ns for ns,name in markers}
        opt_a=boundaries['embedded_begin']
        opt_b=boundaries['embedded_options_complete']
        options=[(max(opt_a,a),min(opt_b,b)) for a,b in spans[4170]+spans[4178] if max(opt_a,a)<min(opt_b,b)]
        row['option_functions_ms']=duration(options)
        row['early_outside_option_functions_ms']=(opt_b-opt_a)/1e6-row['option_functions_ms']
        intervals=[v for k,v in row.items() if ' → ' in k and k.endswith(' excl InnoDB+Aria')]
        assert abs(sum(intervals)-row['embedded_outside_engines_ms'])<1e-8
        assert all(v>=-1e-8 for v in intervals)
        for n,entries in spans.items():
            chosen=entries if n==5749 else embedded(entries)
            calls.append(dict(block=block,fork=i,fn=n,name=scopes[str(n)],calls=len(chosen),ms=duration(chosen)))
        rows.append(row)
    assert i==21
assert len(suites)==12 and len(rows)==84 and len(calls)==84*len(scopes)
table('suites',suites);table('intervals',rows);table('functions-by-fork',calls)
agg=[]
def summarize(kind,key,vals):
    agg.append(dict(kind=kind,phase=key,median_ms=stat.median(vals),min_ms=min(vals),max_ms=max(vals),
        min_trial_median_ms=min(stat.median(vals[i:i+21]) for i in range(0,len(vals),21)),
        max_trial_median_ms=max(stat.median(vals[i:i+21]) for i in range(0,len(vals),21))))
for key in rows[0]:
    if key not in ('fold','block','fork'):summarize('marker',key,[r[key] for r in rows])
for n,name in scopes.items():
    summarize('function',n+' '+name,[r['ms'] for r in calls if r['fn']==int(n)])
table('summary',agg)
for r in agg:print(r['phase'],round(r['median_ms'],4),round(r['min_trial_median_ms'],4),round(r['max_trial_median_ms'],4))
