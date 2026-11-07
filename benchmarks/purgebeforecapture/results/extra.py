from pathlib import Path
import json,gzip,statistics,math,sys
p=Path(__file__).parent
obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));records=json.loads((p/'records.json').read_text());out=[]
def stats(v):
 z=sorted(v);return dict(mean=statistics.mean(z),p50=statistics.median(z),p95=z[math.ceil(.95*len(z))-1],n=len(z))
for arm in ['now','drain']:
 rr=[r for r in records if r['kind']=='primary' and r['arm']==arm];vs=[obs[r['report']] for r in rr];spans={}
 for r in vs:
  for s in r['samples']:
   for v in s['spans']:spans.setdefault(v['name'],[]).append(v['end_ms']-v['begin_ms'])
 out.append(dict(arm=arm,child_spans={k:stats(v) for k,v in spans.items()},suite_ms=stats([v['suite_ms'] for v in vs]),batch_ms=stats([v['batch_ms'] for v in vs]),suite_cpu_ms=stats([v['suite_cpu_ms'] for v in vs]),batch_cpu_ms=stats([v['batch_cpu_ms'] for v in vs]),lifetime_max_rss_bytes=stats([v['lifetime_max_rss_bytes'] for v in vs]),fork_cpu_ms=stats([s['fork_cpu_ms'] for v in vs for s in v['samples']])))
if '--check' in sys.argv:assert out==json.loads((p/'extra-summary.json').read_text());print('PASS: full suite, child spans, CPU and lifetime RSS replay')
else:(p/'extra-summary.json').write_text(json.dumps(out,indent=2)+'\n')
