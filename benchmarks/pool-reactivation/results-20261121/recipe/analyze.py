"""Validate data, reconstruct costs and simultaneous response distributions."""
import csv
import json
import math
from pathlib import Path
import statistics
import sys

out=Path(sys.argv[1])
waves=[]
requests=[]
def save(name,data):
    with (out/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=data[0].keys(),lineterminator='\n')
        w.writeheader()
        for row in data:
            w.writerow({k:round(v,5) if isinstance(v,float) else v for k,v in row.items()})
def pct95(values):
    return sorted(values)[math.ceil(len(values)*.95)-1]
for block in range(1,5):
    order=('current','split') if block%2 else ('split','current')
    for pos,arm in enumerate(order):
        r=json.loads((out/f'main-{block}-{pos}-{arm}.json').read_bytes())
        assert r['Armed']==9 and r['Period']==(400 if arm=='current' else 50)
        assert r['LowWrites']>=1 and len(r['Waves'])==9
        assert len(r['InitialStocks'])==8 and r['After']==[[40,100,1888173,1888173]]*8
        stock=r['InitialStocks'].copy()
        for index,v in enumerate(r['Waves']):
            phase='long' if index==8 else 'short'
            intended=69+block+.25 if phase=='long' else 8
            a,z=v['BeforeIdle'],v['AfterIdle']
            dt=z['Seconds']-a['Seconds']
            assert v['IdleSeconds']==intended and abs(dt-intended)<1
            assert all(z[k]>=a[k] for k in a)
            def delta(k): return z[k]-a[k]
            ws=v['Wakes']
            assert len(ws)==8 and v['AllResponsesMS']==max(w['EndMS'] for w in ws)
            starts=[w['StartMS'] for w in ws]
            ends=[w['EndMS'] for w in ws]
            for i,w in enumerate(ws):
                assert w['ID']==i+2 and w['Write']==((i%2==1) != ((index%2==1) != (block%2==0)))
                assert 0<=w['ConnectMS']<=w['TotalMS'] and 0<=w['SQLMS']<=w['TotalMS']
                assert abs(w['StartMS']+w['TotalMS']-w['EndMS'])<.0001
                assert w['Before']['SinceTickMS']>=0
                stock[i]+=int(w['Write'])
                requests.append(dict(block=block,arm=arm,wave=index+1,phase=phase,db=i+1,sql='update' if w['Write'] else 'select',
                                     low=w['Before']['Low'],age_ms=w['Before']['SinceTickMS'],start_ms=w['StartMS'],connect_ms=w['ConnectMS'],
                                     sql_ms=w['SQLMS'],total_ms=w['TotalMS'],end_ms=w['EndMS']))
            waves.append(dict(block=block,arm=arm,wave=index+1,phase=phase,idle_s=dt,cpu_ms=(delta('UserUS')+delta('SystemUS'))/1000,
                    irq=delta('Interrupts'),pkg=delta('PackageIdle'),ticks=delta('Ticks'),starts_low=sum(w['Before']['Low'] for w in ws),
                    to_low=delta('SetLow'),to_high=delta('SetHigh'),new_workers=delta('Starts'),
                    start_spread_ms=max(starts)-min(starts),all_in_flight=max(starts)<min(ends),all_ms=max(ends)))
        assert stock==r['FinalStocks']
# A common 4-second reference makes long callback gaps visible in both arms.
# It is the configured idle period; it is not a timeout or an exclusion rule.
ages=[]
for arm in ('current','split'):
    for block in range(1,5):
        for db in range(1,9):
            vals=[r for r in requests if (r['arm'],r['block'],r['db'])==(arm,block,db)]
            on=[r['age_ms'] for r in vals if not r['low']]
            off=[r['age_ms'] for r in vals if r['low']]
            ages.append(dict(arm=arm,block=block,db=db,on_samples=len(on),max_on_ms=max(on,default=0),
                             low_samples=len(off),max_low_ms=max(off,default=0),on_over_4s=sum(t>4000 for t in on)))
save('timer-ages',ages)
save('requests',requests)
save('waves',waves)
def rates(rows):
    t=sum(r['idle_s'] for r in rows)
    return {k+'_s':sum(r[k] for r in rows)/t for k in ('cpu_ms','irq','pkg','ticks')}
trials=[]; summary=[]
for phase in ('short','long'):
    for arm in ('current','split'):
        group=[v for v in waves if v['phase']==phase and v['arm']==arm]
        req=[r for r in requests if r['phase']==phase and r['arm']==arm]
        rates_by_block=[]
        for block in range(1,5):
            g=[v for v in group if v['block']==block]
            rr=rates(g)
            rates_by_block.append(rr)
            trials.append(dict(phase=phase,arm=arm,block=block,**rr,rounds=len(g),max_ms=max(r['all_ms'] for r in g)))
        rr={k:statistics.mean(v[k] for v in rates_by_block) for k in rates_by_block[0]}
        completion=[r['all_ms'] for r in group]
        summary.append(dict(phase=phase,arm=arm,rounds=len(group),requests=len(req),starts_low=sum(r['low'] for r in req),**rr,
                    barrier_median_ms=statistics.median(completion),barrier_p95_ms=pct95(completion),barrier_max_ms=max(completion),
                    request_max_ms=max(r['total_ms'] for r in req),select_max_ms=max(r['total_ms'] for r in req if r['sql']=='select'),
                    update_max_ms=max(r['total_ms'] for r in req if r['sql']=='update'),
                    slow_requests=sum(r['total_ms']>=400 for r in req),slow_rounds=sum(v>=400 for v in completion),
                    overlap=sum(r['all_in_flight'] for r in group),max_start_spread_ms=max(r['start_spread_ms'] for r in group)))
save('trials',trials);save('summary',summary)
# Distinguish early active intervals from short intervals after the pool has
# crossed its own inactivity threshold despite light application requests.
by_wave=[]
for arm in ('current','split'):
    for i in range(1,10):
        part=[v for v in waves if v['arm']==arm and v['wave']==i]
        by_wave.append(dict(arm=arm,wave=i,requests=len(part)*8,starts_low=sum(v['starts_low'] for v in part),
                            low_switches=sum(v['to_low'] for v in part),high_switches=sum(v['to_high'] for v in part),
                            **rates(part)))
save('by-wave',by_wave)
print('PASS: 8 processes, 72 barrier releases, 576 checked first statements, 64 final stock and order checks')
