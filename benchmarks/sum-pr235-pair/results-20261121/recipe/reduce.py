from pathlib import Path
import json,csv
from statistics import mean,median
out=Path('evidence')
rows=[]
for group in range(1,7):
    order=('os','ring','os') if group%2 else ('ring','os','ring')
    times=[]
    for index,arm in enumerate(order,1):
        file=out/'runs'/f'{group}-{index}-{arm}.jsonl'
        header,*dbs=map(json.loads,file.read_text().splitlines())
        assert header['arm']=='A' and len(dbs)==12
        assert all(r['db']==i and r['inserts']==100 and r['close']=='pass' for i,r in enumerate(dbs))
        times.append(mean(r['raw_ns'] for r in dbs[2:])/1e6)
    os,ring=[mean(t for t,a in zip(times,order) if a==arm) for arm in ('os','ring')]
    rows.append(dict(group=group,order='/'.join(order),first_ms=times[0],middle_ms=times[1],last_ms=times[2],
        os_ms=os,ring_ms=ring,saved_ms=os-ring,saved_pct=100*(os-ring)/os,noise_ms=abs(times[2]-times[0])))
with (out/'pairs.csv').open('w') as f:
    wr=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');wr.writeheader();wr.writerows(rows)
def med(key):return median(r[key] for r in rows)
n=sum(r['saved_ms']>0 for r in rows)
s=dict(os_ms=med('os_ms'),ring_ms=med('ring_ms'),saved_ms=med('saved_ms'),saved_pct=med('saved_pct'),noise_ms=med('noise_ms'),positive=n,passed=n==6 and med('saved_ms')>med('noise_ms'))
(out/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
print(s)
