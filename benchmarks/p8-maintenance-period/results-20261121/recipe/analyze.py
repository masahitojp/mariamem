"""Check workload, pairing and timer readback; aggregate process-level outcomes."""
import csv
import gzip
import itertools
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

out=Path(sys.argv[1])
rows=[];loads=[]
def write(name,records):
    with (out/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n')
        w.writeheader();w.writerows(records)
def q(values,frac):return sorted(values)[math.ceil(frac*len(values))-1]
def median(values):return round(statistics.median(values),4)
def ci_median(values):
    n=len(values);x=sorted(values)
    k=next(i for i in range(n) if sum(math.comb(n,j) for j in range(i+1))/2**n>0.025)
    return [round(x[k],4),round(x[-k-1],4)]
for path in sorted((out/'runs').glob('main-*.gz')):
    r=json.loads(gzip.decompress(path.read_bytes()))
    mode,arm,period=r['mode'],r['arm'],r['period']
    ident=dict(mode=mode,setting=arm,period=period,block=r['block'],position=r['position'])
    assert r['armed']==22
    assert r['counts']['read']==50 and r['counts']['write']==20 and r['counts']['sample']==21 and r['counts']['fork']==21
    assert len(r['windows'])==21 and r['armed']>0
    values=[]
    for lane,w in r['windows'].items():
        v=(w['end']-w['start'])/1e6
        values.append(v);loads.append(dict(**ident,lane=lane,sample_ms=v))
    metrics=dict(starts=None,ticks=None,max_first_ms=None,max_completion_ms=None,total_first=None)
    if mode=='diag':
        assert r['settings'].keys()==r['windows'].keys()
        dbs=list(r['dbs'].values())
        for cfg in r['settings'].values():
            assert cfg['before'][4]=='ON' and cfg['after'][4]==('ON' if arm=='default' else 'OFF')
        assert all(d['worker_starts']>0 for d in dbs)
        for d in dbs:
            if d['worker_events']:
                assert sum(e[1]==9 for e in d['worker_events'])==d['worker_starts']
                assert sum(e[1]==19 for e in d['worker_events'])==d['maintenance_calls']
        metrics=dict(starts=sum(d['worker_starts'] for d in dbs),ticks=sum(d['maintenance_calls'] for d in dbs),
                     max_first_ms=max(d['max_first_ns'] for d in dbs)/1e6,
                     max_completion_ms=max(d['max_completion_ns'] for d in dbs)/1e6,total_first=sum(d['first_count'] for d in dbs))
    rows.append(dict(**ident,armed=r['armed'],suite_ms=r['suite_ms'],cpu_ms=r['cpu_ms'],max_load_ms=max(values),
                     tails=sum(v>=400 for v in values),**metrics))
summary=[];paired=[]
for mode in ('diag','raw'):
    settings=('default','off') if mode=='diag' else ('default',)
    cases=[(s,p) for s in settings for p in (400,50)]
    orders=list(itertools.permutations(cases))
    for block in range(1,97):
        block_rows=sorted((r for r in rows if r['mode']==mode and r['block']==block),key=lambda r:r['position'])
        assert [(r['setting'],r['period']) for r in block_rows]==list(orders[(block-1)%len(orders)])
    for arm in settings:
        by_period={}
        for per in (400,50):
            data=sorted((r for r in rows if (r['mode'],r['setting'],r['period'])==(mode,arm,per)),key=lambda r:r['block'])
            assert len(data)==96
            by_period[per]=data
            summary.append(dict(mode=mode,setting=arm,period=per,suites=96,loads=2016,tail_suites=sum(r['tails']>0 for r in data),
                tail_loads=sum(r['tails'] for r in data),max_load_ms=max(r['max_load_ms'] for r in data),
                p95_suite_max_ms=q([r['max_load_ms'] for r in data],0.95),median_wall_ms=median([r['suite_ms'] for r in data]),
                median_cpu_ms=median([r['cpu_ms'] for r in data]),median_starts=median([r['starts'] for r in data]) if mode=='diag' else None,
                total_starts=sum(r['starts'] for r in data) if mode=='diag' else None,total_ticks=sum(r['ticks'] for r in data) if mode=='diag' else None,
                max_first_ms=max(r['max_first_ms'] for r in data) if mode=='diag' else None,max_completion_ms=max(r['max_completion_ms'] for r in data) if mode=='diag' else None))
        pairs=list(zip(by_period[400],by_period[50]))
        for metric in ('cpu_ms','suite_ms','max_load_ms')+(('starts','ticks') if mode=='diag' else ()):
            ratios=[100*(b[metric]/a[metric]-1) for a,b in pairs if a[metric]]
            diffs=[b[metric]-a[metric] for a,b in pairs]
            paired.append(dict(mode=mode,setting=arm,metric=metric,absolute_median=median(diffs),paired_pct=median(ratios) if ratios else None,
                pct_ci=ci_median(ratios) if ratios else None,lower=sum(d<0 for d in diffs),equal=sum(d==0 for d in diffs),n=len(diffs)))
        if mode=='raw':
            ordinary=[100*(b['cpu_ms']/a['cpu_ms']-1) for a,b in pairs if not a['tails'] and not b['tails']]
            paired.append(dict(mode=mode,setting=arm,metric='cpu_ms_both_below_400',absolute_median=median([b['cpu_ms']-a['cpu_ms'] for a,b in pairs if not a['tails'] and not b['tails']]),paired_pct=median(ordinary),
                pct_ci=ci_median(ordinary),lower=sum(d<0 for d in ordinary),equal=sum(d==0 for d in ordinary),n=len(ordinary)))
        only400=sum(a['tails']>0 and b['tails']==0 for a,b in pairs)
        only50=sum(b['tails']>0 and a['tails']==0 for a,b in pairs)
        n=only400+only50
        exact=min(1,2*sum(math.comb(n,i) for i in range(min(only400,only50)+1))/2**n)
        print(mode,arm,'discordant blocks 400-only/50-only',only400,only50,'two-sided exact p',exact)
assert len(rows)==576 and len(loads)==12096
write('suites.csv',rows);write('loads.csv',loads);write('summary.csv',summary);write('paired.csv',paired)
print('PASS: 576 measured suites; balanced 96 blocks per mode; 12,096 sample loads; each suite checked timer arm, counts, settings where instrumented.')
