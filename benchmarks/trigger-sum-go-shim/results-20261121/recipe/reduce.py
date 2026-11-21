from pathlib import Path
import csv
import json
import statistics
import sys
out=Path(sys.argv[1]); observations=[json.loads(line) for line in (out/'observations.jsonl').read_text().splitlines()]
assert len(observations)==42
processes={};bydb=0
expected=[(0,s,a) for a in ('base','shim') for s in 'ABC']+[
    (i,s,a) for i,order in enumerate(('ABC','BCA','CAB')*2,1) for s in order
    for a in (('base','shim') if i%2 else ('shim','base'))]
assert [(o['block'],o['sql'],o['arm']) for o in observations]==expected
for o in observations:
    records=o['rows'][1:]
    assert len(records)==(43 if o['block'] else 1)
    assert all(r['db']==i and r['inserts']==100 and r['close']=='pass' for i,r in enumerate(records))
    bydb+=len(records)
    if not o['block']:continue
    selected=records[3:]
    times=[r['raw_ns']/1e6 for r in selected]
    cpu=[r['process_cpu_ns']/1e6 for r in selected]
    processes[o['block'],o['sql'],o['arm']]={'raw_ms':statistics.median(times),'cpu_ms':statistics.median(cpu),'p95_ms':sorted(times)[37]}
pairs=[]; summary=[]
for s in 'ABC':
    current=[]
    for i in range(1,7):
        a,b=[processes[i,s,arm] for arm in ('base','shim')]
        row={'block':i,'sql':s,'first':'base' if i%2 else 'shim'}
        for metric in a:
            row['base_'+metric]=round(a[metric],6)
            row['shim_'+metric]=round(b[metric],6)
            row[metric+'_gain_pct']=round(100*(1-b[metric]/a[metric]),5)
        current.append(row)
    pairs+=current
    row={'sql':s,'pairs':6}
    for k in ('raw_ms','cpu_ms','p95_ms'):
        gains=[r[k+'_gain_pct'] for r in current]
        row[k+'_shorter']=sum(x>0 for x in gains)
        row[k+'_median_gain_pct']=round(statistics.median(gains),5)
        row[k+'_min_gain_pct']=min(gains);row[k+'_max_gain_pct']=max(gains)
    summary.append(row)
assert bydb==1554
for name,rows in [('pairs',pairs),('summary',summary)]:
    with (out/(name+'.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
