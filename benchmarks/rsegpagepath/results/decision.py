from pathlib import Path
import json,statistics,sys
from stage_core import stats
p=Path(__file__).parent;s=json.loads((p/'summary.json').read_text());pr={r['name']:r for r in s['processes']}
leaves=['header.lookup','header.read.frame_init','header.read.sync_io_request','header.read.read_complete','header.read.race_read_wait','header.read.other','header.random_read_ahead','header.read_wait','header.other','header.wrapper']
keys=['api_startup','rseg_array','rseg.page.rseg_header','header.sync_read_miss']+leaves
cells=[]
for mode in ['fresh','fork']:
 rows=[r for r in s['children'] if r['run'] in pr and pr[r['run']]['mode']==mode];assert len(rows)==144
 for r in rows:assert abs(sum(r['ms'][k] for k in leaves)-r['ms']['rseg.page.rseg_header'])<1e-6
 metrics={k:stats([r['ms'][k] for r in rows]) for k in keys}
 ratios={k:stats([r['ms'][k]/r['ms']['rseg.page.rseg_header'] for r in rows]) for k in leaves}
 counts={k:dict(min=min(r['ms'][k] for r in rows),max=max(r['ms'][k] for r in rows),mean=statistics.mean(r['ms'][k] for r in rows)) for k in rows[0]['ms'] if k.startswith('count.header.')}
 cells.append(dict(mode=mode,children=144,metrics=metrics,ratios=ratios,counts=counts,early_late=[dict(run=r['name'],early={k:stats([x['ms'][k] for x in rows if x['run']==r['name'] and x['child']<8]) for k in keys},late={k:stats([x['ms'][k] for x in rows if x['run']==r['name'] and x['child']>=8]) for k in keys}) for r in pr.values() if r['mode']==mode]))
f=next(c for c in cells if c['mode']=='fork');dominant=[k for k in leaves if f['metrics'][k]['p50']>=.5 and f['ratios'][k]['p50']>=.5]
out=dict(result='DOMINANT_PATH_IDENTIFIED' if dominant else 'INCONCLUSIVE',dominant=dominant,criterion='Fork pooled per-child median component >=0.5ms AND median per-child share >=50 percent of rseg-header acquisition',cells=cells,scope='One diagnostic build; attribution only, not optimization/adoption or CPU measurement')
if '--check' in sys.argv:assert out==json.loads((p/'decision.json').read_text());print('PASS decision replay')
else:(p/'decision.json').write_text(json.dumps(out,indent=2)+'\n')
