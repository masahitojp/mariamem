"""Replay validated trials and summarize target-timer progress by DB."""
import csv
import gzip
import json
import sys
from pathlib import Path
from diagnose import check,count,resolved

out=Path(sys.argv[1])
def reports(prefix):
    return sorted(p for p in out.glob(prefix+'-*.json*') if p.name.endswith(('.json','.json.gz')))
def read(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt') as f: return json.load(f)
    return json.loads(path.read_bytes())
def write(name,rows):
    with (out/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n')
        w.writeheader();w.writerows(rows)
for p in reports('pilot'):
    check(read(p),True)
assert len(reports('pilot'))==2
files=reports('main')
assert len(files) in (2,4,6,8)
blocks=len(files)//2
summary=[];finals=[];snapshots=[];gaps=[];bound={}
for block in range(1,blocks+1):
    order=('current','split') if block%2 else ('split','current')
    found=False
    for pos,arm in enumerate(order):
        p=next(p for p in files if p.name.split('.')[0]==f'main-{block}-{pos}-{arm}')
        r=read(p)
        assert r['Period']==(400 if arm=='current' else 50)
        observations=check(r)
        for gap in observations:
            gaps.append(dict(block=block,arm=arm,**gap))
        found=found or any(resolved(g) for g in observations)
        for i,v in enumerate(r['Waves'],1):
            assert abs(v['AfterIdle']['Seconds']-v['BeforeIdle']['Seconds']-(8 if i<9 else 69+block+.25))<1
            assert len([w for w in v['Wakes'] if w['Write']])==4
            for db,(path,w) in enumerate(zip(v['Paths'],v['Wakes']),1):
                c=path['Counters']
                route_age=(path['NowNS']-c['maintenance_enter']['Last']['AtNS'])/1e6
                values=dict(block=block,arm=arm,wave=i,db=db,low=path['Old']['Low'],age_ms=round(path['Old']['SinceTickMS'],4),
                            route_age_ms=round(route_age,4),handler=path['Handler']['Kind'],
                            target_handler=path['Handler']['Address']==path['Timer']+8,
                            dispatch=count(path,'dispatch'),execute=count(path,'execute_enter'),entered=count(path,'maintenance_enter'),
                            returned=count(path,'maintenance_return'),reinserted=count(path,'reinsert_done'),
                            worker_submits=count(path,'submit_worker_task_enter'),disarmed=count(path,'disarm_enter'),mismatches=path['KeyMismatches'],
                            sql_total_ms=round(w['TotalMS'],4),all_ms=round(v['AllResponsesMS'],4))
                snapshots.append(values)
                if i==9: finals.append(values)
    bound[block]=found
assert not any(bound[b] for b in range(1,blocks)) and (blocks==4 or bound[blocks])
for arm in ('current','split'):
    vals=[r for r in snapshots if r['arm']==arm]
    final=[r for r in finals if r['arm']==arm]
    summary.append(dict(arm=arm,processes=blocks,forks=len(final),requests=len(vals),stale_DBS=len({(g['block'],g['db']) for g in gaps if g['arm']==arm}),
                  max_normal_ms=max((r['age_ms'] for r in vals if not r['low']),default=0),
                  max_low_ms=max((r['age_ms'] for r in vals if r['low']),default=0),
                  dispatch=sum(r['dispatch'] for r in final),execute=sum(r['execute'] for r in final),
                  entered=sum(r['entered'] for r in final),returned=sum(r['returned'] for r in final),
                  reinserted=sum(r['reinserted'] for r in final),worker_submits=sum(r['worker_submits'] for r in final),
                  mismatches=sum(r['mismatches'] for r in final),max_wave_ms=max(r['all_ms'] for r in vals)))
write('snapshots',snapshots);write('summary',summary)
(out/'anomalies.json').write_text(json.dumps(gaps,indent=2)+'\n')
print('verified',blocks,'pairs,',len(snapshots),'per-DB observations,',len(gaps),'stale or identity observations')
