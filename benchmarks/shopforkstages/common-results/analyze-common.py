"""Read-only replay of retained common-startup observations."""
from pathlib import Path
import gzip,json,statistics,sys
from common import partition,BUCKETS
from decompose import events
E=Path(__file__).resolve().parent
path=E/'observations.json.gz'
rows=json.loads(gzip.decompress(path.read_bytes()) if path.exists() else (E/'observations.json').read_bytes())
assert len(rows)==16 and all(r['accepted'] for r in rows)
expected={(r,p,m) for r in range(-1,3) for p in [4,8] for m in ['off','on']}
assert {(r['repeat'],r['parallel'],r['mode']) for r in rows}==expected

def stats(values):
 v=sorted(values);assert v
 def q(p):
  x=(len(v)-1)*p;i=int(x);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)
 return dict(n=len(v),p50=statistics.median(v),p95=q(.95),mean=statistics.mean(v),max=max(v),over100ms=sum(x>100 for x in v))

def forks(row):return [s['end_ms']-s['start_ms'] for s in row['trace']['spans'] if s['kind']=='fork']
# Trace span schema is checked before reading any aggregate.
for r in rows:
 assert r['scratch_empty'] and r['exit_code']==0
 assert r['trace']['meta']['active_mappings_after']=='0'
 assert len(forks(r))==21

def child_parts(row):
 assert row['mode']=='on'
 return [partition(v) for lane,v in row['stages'].items() if lane!='root']

out={'result':'COMPLETE_BOUNDED_OBSERVATION','primary_children_per_cell':63,'cells':{},'observer_pairs':{},'processes':[]}
for par in [4,8]:
 for mode in ['off','on']:
  cell=[r for r in rows if r['repeat']>=0 and r['parallel']==par and r['mode']==mode]
  assert len(cell)==3
  c=dict(fork_ms=stats([x for r in cell for x in forks(r)]),suite_ms=stats([r['trace']['elapsed_ms'] for r in cell]))
  if mode=='on':
   ps=[p for r in cell for p in child_parts(r)];assert len(ps)==63
   c['common_ms']={k:stats([p[k] for p in ps]) for k in ps[0] if k!='clock_metadata'}
   c['sum_share_percent']={k:sum(p[k] for p in ps)/sum(p['total'] for p in ps)*100 for k in BUCKETS+['charset_inclusive','other_excluding_charset']}
   c['clock_metadata_unique']={k:sorted({json.dumps(p['clock_metadata'][k],sort_keys=True) for p in ps}) for k in ps[0]['clock_metadata']}
  out['cells'][f'p{par}-{mode}']=c
 pairs=[]
 for repeat in range(3):
  a=next(r for r in rows if r['parallel']==par and r['mode']=='off' and r['repeat']==repeat)
  b=next(r for r in rows if r['parallel']==par and r['mode']=='on' and r['repeat']==repeat)
  pairs.append(dict(repeat=repeat,fork_p50_on_minus_off=statistics.median(forks(b))-statistics.median(forks(a)),suite_on_minus_off=b['trace']['elapsed_ms']-a['trace']['elapsed_ms']))
 out['observer_pairs'][f'p{par}']=pairs
for r in rows:
 v=dict(name=r['name'],fork_ms=stats(forks(r)),suite_ms=r['trace']['elapsed_ms'])
 if r['mode']=='on':
  ps=child_parts(r);v['common_ms']={k:stats([p[k] for p in ps]) for k in BUCKETS+['other','total']}
 out['processes'].append(v)
if '--check' in sys.argv:
 assert out==json.loads((E/'summary.json').read_text());print('PASS retained observations replay')
else: print(json.dumps(out,indent=2))
