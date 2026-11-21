"""Check complete paired samples against the original observations."""
import csv,itertools,json,math,statistics,sys
from pathlib import Path
from collections import Counter
out=Path(sys.argv[1]);runs=out/'runs'
def rows(prefix):
    return [json.loads(p.read_bytes()) for p in sorted(runs.glob(prefix+'*.json'))]
def save(name,data):
    with (out/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n')
        w.writeheader();w.writerows(data)
def med(v):return round(statistics.median(v),5)
def rankci(v):
    n=len(v);s=sorted(v)
    k=next(i for i in range(n) if sum(math.comb(n,j) for j in range(i+1))/2**n>.025)
    return [round(s[k],4),round(s[-k-1],4)]
p1=rows('p1-main')
assert len(p1)==96
paired=[];case_summary=[]
for b in range(1,49):
    a,z=sorted((r for r in p1 if r['block']==b),key=lambda r:r['period'],reverse=True)
    assert {a['period'],z['period']}=={50,400} and a['position']==(b+1)%2 and z['position']==b%2
    for r in (a,z):
        assert r['armed']==22 and len(r['loads'])==21 and all(r['counts'][k]==n for k,n in dict(read=50,write=20,sample=21,fork=21).items())
    paired.append(dict(block=b,wall_pct=100*(z['wall_ms']/a['wall_ms']-1),cpu_pct=100*(z['cpu_ms']/a['cpu_ms']-1),maxload_pct=100*(max(z['loads'].values())/max(a['loads'].values())-1)))
save('p1-pairs',paired)
for p in [400,50]:
    these=[r for r in p1 if r['period']==p]
    all_loads=[v for r in these for v in r['loads'].values()]
    case_summary.append(dict(period=p,suites=len(these),loads=len(all_loads),cpu_med_ms=med([r['cpu_ms'] for r in these]),wall_med_ms=med([r['wall_ms'] for r in these]),max_load_ms=max(all_loads),tail_loads=sum(v>=400 for v in all_loads)))
save('p1',case_summary)
# With serial subtests, the 21 sample spans do not overlap.
spans = []
for period in (400, 50):
    trials = [r for r in p1 if r['period'] == period]
    totals = [sum(r['loads'].values()) for r in trials]
    spans.append(dict(
        period=period,
        median_sum_sample_ms=med(totals),
        median_outside_sample_ms=med([r['wall_ms'] - total for r, total in zip(trials, totals)]),
    ))
save('p1-sample-time', spans)
p1_delta={k:dict(median=med([r[k] for r in paired]),ci=rankci([r[k] for r in paired]),lower=sum(r[k]<0 for r in paired)) for k in ['cpu_pct','wall_pct','maxload_pct']}
(out/'p1-delta.json').write_text(json.dumps(p1_delta,indent=2)+'\n')
if len(sys.argv)>2 and sys.argv[2]=='p1':print(p1_delta);sys.exit(0)
idle=rows('idle-');assert len(idle)==8
intervals=[];first_order=[(400,1),(50,1),(50,8),(400,8)]
for b,order in enumerate([first_order,first_order[::-1]],1):
    rs=sorted((r for r in idle if r['block']==b),key=lambda r:r['position'])
    assert [(r['Period'],r['DBs']) for r in rs]==order
    for r in rs:
        assert r['Armed']==r['DBs']+1 and len(r['After'])==r['DBs'] and all(v==r['Expected'] for v in r['After'])
        assert r['Expected'][0:2]==[40,100] and r['Expected'][2]==r['Expected'][3]>0
        for i,(l,h) in enumerate(zip(r['Readings'],r['Readings'][1:])):
            dt=h['Seconds']-l['Seconds']
            assert abs(dt-[30,40,50][i])<1
            diff={k:h[k]-l[k] for k in l if k!='Seconds'}
            assert all(x>=0 for x in diff.values())
            intervals.append(dict(block=b,position=r['position'],period=r['Period'],dbs=r['DBs'],phase=['0–30','30–70','70–120'][i],
                                  seconds=round(dt,5),cpu_ms_s=(diff['UserUS']+diff['SystemUS'])/1000/dt,
                                  irq_s=diff['Interrupts']/dt,pkg_s=diff['PackageIdle']/dt,ticks_s=diff['Ticks']/dt,
                                  switches_low=diff['SetLow'],switches_high=diff['SetHigh'],workers=diff['Starts'],
                                  context_switch_s=(diff['Voluntary']+diff['Involuntary'])/dt))
save('idle-windows',intervals)
summary=[]
for n,p in itertools.product([1,8],[400,50]):
    subset=[r for r in intervals if r['dbs']==n and r['period']==p and r['phase']=='70–120']
    assert len(subset)==2
    m=dict(dbs=n,period=p)
    for k in ['cpu_ms_s','irq_s','pkg_s','ticks_s','context_switch_s']:
        m[k]=med([r[k] for r in subset]);m[k+'_range']=[round(min(r[k] for r in subset),4),round(max(r[k] for r in subset),4)]
    summary.append(m)
save('idle-steady',summary)
# Pool rates are summed across all live forks. Normalize by the number of
# forks for a comparable mean interval per pool; this is not a jitter metric.
phases = []
for n, period, phase in itertools.product([1, 8], [400, 50], ['0–30', '30–70', '70–120']):
    trials = [r for r in intervals if (r['dbs'], r['period'], r['phase']) == (n, period, phase)]
    ticks = statistics.mean(r['ticks_s'] for r in trials)
    phases.append(dict(
        dbs=n, period=period, phase=phase, ticks_per_process_s=round(ticks, 5),
        effective_ms_per_pool=round(1000 * n / ticks, 2) if ticks else None,
        low_transitions_per_run=[r['switches_low'] for r in trials],
        high_transitions_per_run=[r['switches_high'] for r in trials],
        new_workers_per_run=[r['workers'] for r in trials],
    ))
save('idle-phases', phases)
print('PASS: 8 serial 120s idle holds, verified 1 or 8 disconnected forks before and after, 24 distinct intervals; 48 P1 pairs and 2,016 validated loads.')
