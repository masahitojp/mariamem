from pathlib import Path
import csv,gzip,json
from statistics import mean,median
e=Path('evidence');rows=[]
for b in (1,2):
    data=json.loads(gzip.decompress((e/f'fork-{b}.json.gz').read_bytes()))
    ordered=sorted(((int(k[:-5].split('-')[-1]),v) for k,v in data.items() if k!='suite.json'))
    prior=-1;latest=None;i=0
    for seq,v in ordered:
        if v['operation']=='startup':latest=(seq,v)
        if v['operation']!='fork':continue
        i+=1;assert prior<latest[0]<seq;prior=seq
        times={x['name']:x['offset_ns'] for x in latest[1]['events']}
        fork=v['events'][-1]['offset_ns']-v['events'][0]['offset_ns']
        ready=times['ready_header_received']-times['linked_execution_begin']
        assert 0<ready<fork
        rows.append(dict(block=b,db=i,fork_ms=fork/1e6,linked_to_header_ms=ready/1e6,guest_record=bool(latest[1].get('guest'))))
    assert i==21
with (e/'fork-stages.csv').open('w') as f:
    wr=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');wr.writeheader();wr.writerows(rows)
print('per-fork medians',median(r['fork_ms'] for r in rows),median(r['linked_to_header_ms'] for r in rows), 'weighted share',sum(r['linked_to_header_ms'] for r in rows)/sum(r['fork_ms'] for r in rows))
