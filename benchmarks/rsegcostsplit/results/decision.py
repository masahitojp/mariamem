from pathlib import Path
import json,statistics,sys
from stage_core import stats
p=Path(__file__).parent
s=json.loads((p/'summary.json').read_text())
primary={x['name']:x for x in s['processes']}
keys=['rseg_array','rseg.page_total','rseg.page.trx_sys','rseg.page.space_header','rseg.page.rseg_header','rseg.page.history_page','rseg.scan_exclusive','rseg.undo_restore','rseg.residual','api_startup']
cells=[]
for mode in ['fresh','fork']:
 rows=[c for c in s['children'] if c['run'] in primary and primary[c['run']]['mode']==mode]
 assert len(rows)==144
 cells.append(dict(mode=mode,children=144,metrics={k:stats([x['ms'][k] for x in rows]) for k in keys},counts={k:stats([x['ms'][k] for x in rows]) for k in rows[0]['ms'] if k.startswith('count.')},null_ratio=stats([x['ms']['ratio.null_slots'] for x in rows]),early_late=[dict(run=r['name'],early={k:stats([x['ms'][k] for x in rows if x['run']==r['name'] and x['child']<8]) for k in keys},late={k:stats([x['ms'][k] for x in rows if x['run']==r['name'] and x['child']>=8]) for k in keys}) for r in primary.values() if r['mode']==mode]))
f=next(x for x in cells if x['mode']=='fork')
threshold=f['metrics']['rseg.scan_exclusive']['p50']>=.5 and f['null_ratio']['p50']>=.9
out=dict(result='RECOMMEND_PROTOTYPE' if threshold else 'DO_NOT_PROTOTYPE_GROUP_SCAN',threshold='Fork per-child pooled median exclusive scan >=0.5ms AND null fraction >=90%',cells=cells,scope='Diagnostic attribution; no optimization, ordinary speedup, CPU attribution or platform acceptance')
if '--check' in sys.argv:
 assert out==json.loads((p/'decision.json').read_text());print('PASS decision replay')
else:(p/'decision.json').write_text(json.dumps(out,indent=2)+'\n')
