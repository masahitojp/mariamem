"""Read-only summary reproduction: default compare, --write for initial capture."""
from pathlib import Path
import json,statistics,sys
D=Path(__file__).resolve().parent
runs=json.loads((D/'uca-observations.json').read_text());children=[s['common_details'] for r in runs for lane,s in r['startups'].items() if lane!='root'];roots=[r['startups']['root']['common_details'] for r in runs]
keys=sorted(k for k in children[0] if k.startswith('uca_id:'))
assert len(runs)==2 and len(children)==42 and len(keys)==5
assert all(d['uca_deep'][0]==5 for d in children+roots)
assert all(not any(k.startswith('uca_booster:') for k in d) for d in children+roots)
def describe(xs):
 ys=sorted(xs);return dict(n=len(ys),p50_ms=statistics.median(ys)/1e6,p95_nearest_rank_ms=ys[__import__('math').ceil(.95*len(ys))-1]/1e6,max_ms=max(ys)/1e6)
rows=[]
for key in keys:
 weight=key.replace('uca_id:','uca_weights:')
 assert all(d[key][0]==1 and d[weight][0]==1 and 0<=d[weight][1]<=d[key][1] for d in children+roots)
 rows.append(dict(identity=key.removeprefix('uca_id:'),total=describe([d[key][1] for d in children]),weights_inclusive=describe([d[weight][1] for d in children]),outside_weights=describe([d[key][1]-d[weight][1] for d in children]),booster_population_calls=0))
result=dict(result='PASS_BOUNDED_OBSERVATION',forks=42,fresh=2,parallel=4,max_forks=5,sql_cases=140,uca_total=describe([d['uca_deep'][1] for d in children]),weight_coverage_ratio=statistics.median(sum(v[1] for k,v in d.items() if k.startswith('uca_weights:'))/d['uca_deep'][1] for d in children),collations=rows)
out=json.dumps(result,indent=2)+'\n';p=D/'summary.json'
if '--write' in sys.argv:p.write_text(out)
else:assert p.read_text()==out
print(out)
