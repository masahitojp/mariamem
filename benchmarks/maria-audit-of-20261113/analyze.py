from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==18 and all(x['returncode']==0 and x['leaf_pass']==70 for x in rows)
groups={};processes=[]
for x in rows:
 t=json.loads((r/f'{x["arm"]}-{x["repeat"]}-trace.json').read_text());assert sum(v['name']=='test' for v in t['spans'])==70
 a={**x,'sample_ms':s.median(v['end_ms']-v['start_ms'] for v in t['spans'] if v['name']=='sample'),'elapsed_ms':t['elapsed_ms']};assert sum(v['name']=='sample' for v in t['spans'])==21;processes.append(a)
for arm in ['pg-official','maria-of','maria-old']:
 a=[x for x in processes if x['arm']==arm and x['repeat']>=0];assert len(a)==5
 groups[arm]={k:s.median(x[k] for x in a) for k in ['wall_ms','cpu_ms','sample_ms','elapsed_ms']};groups[arm]['sample_range_ms']=[min(x['sample_ms'] for x in a),max(x['sample_ms'] for x in a)]
pairs=[]
for i in range(5):
 a={x['arm']:x for x in processes if x['repeat']==i};pairs.append({'round':i,**{k:a['maria-of'][k]-a['maria-old'][k] for k in ['wall_ms','cpu_ms','sample_ms']}})
out={'groups':groups,'maria_of_minus_old':pairs,'paired_median_ms':{k:s.median(x[k] for x in pairs) for k in ['wall_ms','cpu_ms','sample_ms']},'processes':processes};(r/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='processes'},indent=2));print('PASS:18 processes;1260 leaf tests;21 sample loads/process')
