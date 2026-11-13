from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;d=json.loads((r/'summary.json').read_text());out=[]
for p in [1,8]:
 rows=[]
 for i in range(5):
  a={x['arm']:x for x in d['processes'] if x['parallel']==p and x['repeat']==i};rows.append({'round':i,**{k:(a['maria-on'][k]-a['pg-on'][k])-(a['maria-off'][k]-a['pg-off'][k]) for k in ['raw_insert_ms','sample_probe_ms']}})
 out.append({'parallel':p,'rounds':rows,'paired_median_ms':{k:s.median(x[k] for x in rows) for k in ['raw_insert_ms','sample_probe_ms']}})
(r/'gap-reduction.json').write_text(json.dumps(out,indent=2))
