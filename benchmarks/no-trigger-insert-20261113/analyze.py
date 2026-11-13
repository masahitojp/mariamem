from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==48 and all(x['returncode']==0 and x['leaf_pass']==16 for x in rows);out=[]
for x in rows:
 t=json.loads((r/f'{x["name"]}-trace.json').read_text());a={**x}
 for phase in ['raw_insert','sample_probe']:
  v=[z['end_ms']-z['start_ms'] for z in t['spans'] if z['name']==phase];assert len(v)==8;a[phase+'_ms']=s.median(v);a[phase+'_mean_ms']=s.mean(v)
 assert sum(z['name']=='reader_fork' for z in t['spans'])==1;out.append(a)
groups={};contrasts={}
for p in [1,8]:
 for arm in ['pg-on','pg-off','maria-on','maria-off']:
  a=[x for x in out if x['arm']==arm and x['parallel']==p and x['repeat']>=0];assert len(a)==5;g={k:s.median(x[k] for x in a) for k in ['raw_insert_ms','sample_probe_ms']}
  for k in ['raw_insert_ms','sample_probe_ms']:g[k+'_range']=[min(x[k] for x in a),max(x[k] for x in a)]
  groups[f'p{p}-{arm}']=g
 for target,base in [('pg-off','pg-on'),('maria-off','maria-on'),('maria-off','pg-off')]:
  pairs=[]
  for i in range(5):
   a={x['arm']:x for x in out if x['parallel']==p and x['repeat']==i};pairs.append({'round':i,**{k:a[target][k]-a[base][k] for k in ['raw_insert_ms','sample_probe_ms']}})
  contrasts[f'p{p} {target} minus {base}']={'rounds':pairs,'paired_median_ms':{k:s.median(x[k] for x in pairs) for k in ['raw_insert_ms','sample_probe_ms']}}
d={'groups':groups,'contrasts':contrasts,'processes':out};(r/'summary.json').write_text(json.dumps(d,indent=2));print(json.dumps({k:v for k,v in d.items() if k!='processes'},indent=2));print('PASS48 processes/768 child oracles/384 raw100 INSERT batches/384 full sample loads')
