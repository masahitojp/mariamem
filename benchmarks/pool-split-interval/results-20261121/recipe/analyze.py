"""Rebuild the tables from the spans and per-pool wake measurements."""
import csv
import gzip
import itertools
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

out = Path(sys.argv[1])
stage = sys.argv[2] if len(sys.argv) > 2 else 'all'
arms = ['current','short','split']
orders = list(itertools.permutations(arms))
med = statistics.median

def write(name, rows):
    with (out/(name+'.csv')).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:round(v,5) if isinstance(v,float) else v for k,v in row.items()})

def median_ci(values):
    ordered = sorted(values)
    n = len(values)
    k = next(k for k in range(n) if sum(math.comb(n,i) for i in range(k+1)) > 0.025*2**n)
    return ordered[k], ordered[-1-k]

def analyze_suite(parallel):
    key = 'p'+str(parallel)
    blocks = 48 if parallel==1 else 96
    with gzip.open(out/(key+'-spans.jsonl.gz'), 'rt') as f:
        rows = [json.loads(line) for line in f]
    assert len(rows)==3*(blocks+2)
    assert Counter((r['arm'],r['kind']) for r in rows if r['block']==0)==Counter(itertools.product(arms,['semantics','warm']))
    suites = []
    for block in range(1,blocks+1):
        group = [r for r in rows if r['block']==block]
        assert [r['arm'] for r in group]==list(orders[(block-1)%6])
        for position,row in enumerate(group):
            assert row['parallel']==parallel and row['position']==position and row['armed']==22 and row['kind']=='main'
            spans = row['trace']['spans']
            count = Counter(s['kind'] for s in spans)
            assert all(count[k]==v for k,v in [('sample',21),('fork',21),('read',50),('write',20)])
            def durations(kind):
                return [s['end_ms']-s['start_ms'] for s in spans if s['kind']==kind]
            loads = durations('sample')
            assert len(durations('import'))==1 and len(set(s['lane'] for s in spans if s['kind']=='sample'))==21
            suites.append(dict(block=block, arm=row['arm'], wall=row['trace']['elapsed_ms'], cpu=row['cpu_ms'],
                          load_max=max(loads), load_sum=sum(loads), slow=sum(t>=400 for t in loads), setup_import=durations('import')[0]))
    write(key+'-suites',suites)
    summary = []
    for arm in arms:
        trials = [s for s in suites if s['arm']==arm]
        summary.append(dict(arm=arm, suites=blocks,loads=blocks*21, slow_loads=sum(t['slow'] for t in trials),
                    slow_suites=sum(t['slow']>0 for t in trials), worst_ms=max(t['load_max'] for t in trials),
                    wall_med_ms=med(t['wall'] for t in trials), cpu_med_ms=med(t['cpu'] for t in trials),
                    import_med_ms=med(t['setup_import'] for t in trials), load_sum_med_ms=med(t['load_sum'] for t in trials)))
    write(key+'-summary',summary)
    pairs=[]
    for control, trial in [('current','split'),('short','split'),('current','short')]:
        for metric in ('wall','cpu','setup_import','load_max'):
            deltas=[]
            for block in range(1,blocks+1):
                d={s['arm']:s[metric] for s in suites if s['block']==block}
                deltas.append(100*(d[trial]/d[control]-1))
            lo,hi=median_ci(deltas)
            pairs.append(dict(control=control, trial=trial, metric=metric, paired_pct=med(deltas), low95=lo, high95=hi))
    write(key+'-paired',pairs)
    tail_pairs = []
    for control in ['current', 'short']:
        left = [r['slow'] > 0 for r in suites if r['arm']==control]
        right = [r['slow'] > 0 for r in suites if r['arm']=='split']
        counts = Counter(zip(left,right))
        better, worse = counts[True,False], counts[False,True]
        n = better + worse
        p = min(1., 2*sum(math.comb(n,i) for i in range(min(better,worse)+1))/2**n)
        tail_pairs.append(dict(control=control, trial='split', control_only=better, split_only=worse,
                               both=counts[True,True], neither=counts[False,False], exact_two_sided_p=p))
    write(key+'-tail-pairs',tail_pairs)
    print(key, 'verified',len(suites),'suites')

def analyze_idle():
    windows=[]; wakes=[]
    for b, order in enumerate([arms,arms[::-1]],1):
        for position,arm in enumerate(order):
            r=json.loads((out/f'idle-{b}-{position}-{arm}.json').read_bytes())
            assert r['arm']==arm and r['Armed']==9 and r['DBs']==8 and r['LowWrites']>0
            assert (r['Period'],r['IdleMS'])=={'current':(400,4000),'short':(50,500),'split':(50,4000)}[arm]
            assert r['After']==[[40,100,1888173,1888173]]*8
            assert len(r['Readings'])==4 and len(r['Wakes'])==8
            for i,(a,z) in enumerate(zip(r['Readings'],r['Readings'][1:])):
                dt=z['Seconds']-a['Seconds']
                assert abs(dt-[30,40,50][i])<1
                def delta(k):return z[k]-a[k]
                windows.append(dict(block=b,arm=arm,seconds=['0-30','30-70','70-120'][i],cpu_ms_s=(delta('UserUS')+delta('SystemUS'))/1000/dt,
                    irq_s=delta('Interrupts')/dt,package_s=delta('PackageIdle')/dt,ticks_s=delta('Ticks')/dt,
                    low=delta('SetLow'), high=delta('SetHigh'), workers=delta('Starts')))
            for i,w in enumerate(r['Wakes']):
                assert w['ID']==2+i and w['Write']==((i%2==1)!=(b==2))
                assert w['Before']['SinceTickMS']>=0 and 0<=w['SQLMS']<=w['TotalMS'] and 0<=w['ConnectMS']<=w['TotalMS']
                wakes.append(dict(block=b,arm=arm,id=w['ID'],sql='update' if w['Write'] else 'select',
                         low_before=w['Before']['Low'], since_tick_ms=w['Before']['SinceTickMS'],low_connected=w['Connected']['Low'],
                         connect_ms=w['ConnectMS'],sql_ms=w['SQLMS'],total_ms=w['TotalMS']))
    write('idle-windows',windows); write('wakes',wakes)
    summary=[]; wake_summary=[]
    for arm in arms:
        late=[r for r in windows if r['arm']==arm and r['seconds']=='70-120']
        mean={k:statistics.mean(r[k] for r in late) for k in ['cpu_ms_s','irq_s','package_s','ticks_s']}
        summary.append(dict(arm=arm, **mean))
        for sql in ('select','update'):
            subset=[r for r in wakes if r['arm']==arm and r['sql']==sql]
            wake_summary.append(dict(arm=arm,sql=sql, requests=len(subset), started_low=sum(r['low_before'] for r in subset),
                          median_ms=med(r['total_ms'] for r in subset), max_ms=max(r['total_ms'] for r in subset),
                          sql_max_ms=max(r['sql_ms'] for r in subset), slow=sum(r['total_ms']>=400 for r in subset)))
    write('idle-summary',summary);write('wake-summary',wake_summary)
    print('verified 6 idle holds, 18 windows, 48 wake requests')
if stage in ('all','p8'): analyze_suite(8)
if stage in ('all','p1'): analyze_suite(1)
if stage in ('all','idle'): analyze_idle()
