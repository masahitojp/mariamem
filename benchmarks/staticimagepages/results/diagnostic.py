from pathlib import Path
import gzip,json,sys
from stage_core import child,stats
p=Path(sys.argv[1]);records=json.loads((p/'records.json').read_text());obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));timings=json.loads(gzip.decompress((p/'timings.json.gz').read_bytes()));owners=json.loads((p/'owner-summary.json').read_text())
rows=[];expected={(a,P) for a in ['anonymous','pages'] for P in [1,4]}
for r in records:
 if r['kind']!='diagnostic':continue
 assert (r['arm'],r['parallel']) in expected;expected.remove((r['arm'],r['parallel']))
 report=obs[r['report']];owner=next(v for v in owners if v['name']==r['name']);assert owner['child_indices']==list(range(48)) and owner['truncated']==0
 ds=[child(s,'image' if r['arm']=='pages' else 'anonymous') for s in report['samples']]
 starts={s['traces']['startup']['epoch_ns'] for s in report['samples']};assert len(starts)==48
 ts=timings[r['name']]
 for s in report['samples']:
  assert s['traces']['startup'] in ts.values()
 root=[v for v in ts.values() if v['operation']=='startup' and v['epoch_ns'] not in starts];assert len(root)==1
 rows.append({'name':r['name'],'arm':r['arm'],'parallel':r['parallel'],'metrics':{k:stats([d[k] for d in ds]) for k in ds[0]},'children':ds,'root_trace':root[0]})
assert not expected
out={'processes':rows,'scope':'one diagnostic pair per cell, not performance acceptance','mean_deltas':{str(P):{k:next(v for v in rows if v['parallel']==P and v['arm']=='pages')['metrics'][k]['mean']-next(v for v in rows if v['parallel']==P and v['arm']=='anonymous')['metrics'][k]['mean'] for k in rows[0]['metrics']} for P in [1,4]}}
if '--check' in sys.argv:assert out==json.loads((p/'stages.json').read_text());print('PASS: 192 child partitions and owner identities')
else:(p/'stages.json').write_text(json.dumps(out,indent=2)+'\n')
