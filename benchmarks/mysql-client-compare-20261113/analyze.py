from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==48 and all(x['returncode']==0 and x['leaf_pass']==8 for x in rows);out=[]
for x in rows:
 t=json.loads((r/f'{x["name"]}-trace.json').read_text());v=[z['end_ms']-z['start_ms'] for z in t['spans'] if z['name']=='raw_insert'];assert len(v)==8;assert sum(z['name']=='reader_fork' for z in t['spans'])==1;out.append({**x,'raw_ms':s.median(v),'raw_mean_ms':s.mean(v)})
groups={};contrasts={}
for p in [1,8]:
 for arm in ['pg','standard','stdlib','native']:
  a=[x for x in out if x['parallel']==p and x['arm']==arm and x['repeat']>=0];assert len(a)==5;v=[x['raw_ms'] for x in a];groups[f'p{p}-{arm}']={'raw_ms':s.median(v),'range_ms':[min(v),max(v)],'all_ms':v}
 for target,base in [('stdlib','standard'),('native','standard'),('native','stdlib')]:
  a=[]
  for i in range(5):
   q={x['arm']:x for x in out if x['parallel']==p and x['repeat']==i};a.append({'round':i,'delta_ms':q[target]['raw_ms']-q[base]['raw_ms'],'pct':100*(q[target]['raw_ms']/q[base]['raw_ms']-1)})
  contrasts[f'p{p} {target} minus {base}']={'rounds':a,'paired_median_ms':s.median(x['delta_ms'] for x in a),'paired_median_pct':s.median(x['pct'] for x in a)}
d={'groups':groups,'contrasts':contrasts,'processes':out};(r/'summary.json').write_text(json.dumps(d,indent=2));print(json.dumps({k:v for k,v in d.items() if k!='processes'},indent=2));print('PASS48 processes/384 child DB oracles/38400 timed INSERTs')
