from pathlib import Path
import json,gzip,sys
p=Path(sys.argv[1]);obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));records=json.loads((p/'records.json').read_text());rows=[]
for r in records:
 if r['kind']!='primary' or r['parallel']!=4:continue
 report=obs[r['report']];forks=[(s['index'],next(z for z in s['spans'] if z['name']=='start_or_fork')) for s in report['samples']];tails=[]
 for s in report['samples']:
  for z in s['spans']:
   if z['name'] in ['count_sum','update'] and z['end_ms']-z['begin_ms']>100:
    overlap=[i for i,f in forks if max(z['begin_ms'],f['begin_ms'])<min(z['end_ms'],f['end_ms'])]
    tails.append(dict(child=s['index'],stage=z['name'],ms=z['end_ms']-z['begin_ms'],overlapping_fork_children=overlap,count=len(overlap)))
 overlap_sum=sum(max(0,min(a['end_ms'],b['end_ms'])-max(a['begin_ms'],b['begin_ms'])) for i,a in forks for j,b in forks)
 duration=sum(f['end_ms']-f['begin_ms'] for i,f in forks)
 rows.append(dict(name=r['name'],arm=r['arm'],rep=r['rep'],sql_tails=tails,fork_call_overlap_weighted=overlap_sum/duration))
out={'scope':'descriptive existing-data timeline only; no tail removal or causal assignment','rows':rows}
if '--check' in sys.argv:assert out==json.loads((p/'p4-schedule.json').read_text());print('PASS: retained P4 scheduling replay')
else:(p/'p4-schedule.json').write_text(json.dumps(out,indent=2)+'\n')
