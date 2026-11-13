from pathlib import Path
import json,statistics,csv
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==18
assert all(x['returncode']==0 and x['leaf_pass']==70 and x['cpu_ms']>0 for x in rows)
summary={}
for arm in ['pgmem','baseline','candidate']:
 a=[x for x in rows if x['arm']==arm and x['repeat']>=0];assert len(a)==5
 d={k:statistics.median(x[k] for x in a) for k in ['wall_ms','cpu_ms','user_ms','system_ms']};d['wall_range_ms']=[min(x['wall_ms'] for x in a),max(x['wall_ms'] for x in a)]
 for phase in ['elapsed','boot','import','snapshot','fork','sample','test']:
  v=[]
  for x in a:
   t=json.loads((r/f'{arm}-{x["repeat"]}-trace.json').read_text());assert sum(s['name']=='test' for s in t['spans'])==70
   v.append(t['elapsed_ms'] if phase=='elapsed' else statistics.median(s['end_ms']-s['start_ms'] for s in t['spans'] if s['name']==phase))
  d[phase+'_ms']=statistics.median(v)
 summary[arm]=d
pairs=[]
for i in range(5):
 a={x['arm']:x for x in rows if x['repeat']==i};pairs.append({'round':i,'candidate_vs_pgmem_wall_pct':100*(a['candidate']['wall_ms']/a['pgmem']['wall_ms']-1),'candidate_vs_baseline_wall_pct':100*(a['candidate']['wall_ms']/a['baseline']['wall_ms']-1),'candidate_vs_pgmem_cpu_pct':100*(a['candidate']['cpu_ms']/a['pgmem']['cpu_ms']-1),'candidate_vs_baseline_cpu_pct':100*(a['candidate']['cpu_ms']/a['baseline']['cpu_ms']-1)})
out={'groups':summary,'pairs':pairs,'paired_medians_pct':{k:statistics.median(x[k] for x in pairs) for k in pairs[0] if k!='round'}}
(r/'summary.json').write_text(json.dumps(out,indent=2))
with (r/'runs.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(out,indent=2));print('PASS: 18 processes, 1260 leaf assertions, five rotated triplets')
