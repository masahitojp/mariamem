from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==30 and all(x['returncode']==0 and x['leaf_pass']==70 for x in rows);processes=[];arms=['pg-sum','pg-incremental','maria-sum','maria-incremental','maria-cover']
for x in rows:
 t=json.loads((r/f'{x["arm"]}-{x["repeat"]}-trace.json').read_text());assert sum(v['name']=='test' for v in t['spans'])==70;assert sum(v['name']=='sample' for v in t['spans'])==21;assert sum(v['name']=='reader_fork' for v in t['spans'])==1
 a={**x,'elapsed_ms':t['elapsed_ms']}
 for phase in ['sample','test','import','snapshot','boot','reader_fork']:
  a[phase+'_ms']=s.median(v['end_ms']-v['start_ms'] for v in t['spans'] if v['name']==phase)
 processes.append(a)
groups={}
for arm in arms:
 a=[x for x in processes if x['arm']==arm and x['repeat']>=0];assert len(a)==5;groups[arm]={k:s.median(x[k] for x in a) for k in ['wall_ms','cpu_ms','sample_ms','test_ms','elapsed_ms','import_ms','snapshot_ms','boot_ms','reader_fork_ms']};groups[arm]['sample_range_ms']=[min(x['sample_ms'] for x in a),max(x['sample_ms'] for x in a)];groups[arm]['wall_range_ms']=[min(x['wall_ms'] for x in a),max(x['wall_ms'] for x in a)]
contrasts={};metrics=['wall_ms','cpu_ms','sample_ms']
for target,base in [('pg-incremental','pg-sum'),('maria-incremental','maria-sum'),('maria-cover','maria-sum'),('maria-sum','pg-sum'),('maria-incremental','pg-incremental')]:
 a=[]
 for i in range(5):
  q={x['arm']:x for x in processes if x['repeat']==i};a.append({'round':i,**{k:q[target][k]-q[base][k] for k in metrics}})
 contrasts[target+' minus '+base]={'rounds':a,'paired_median_ms':{k:s.median(x[k] for x in a) for k in metrics}}
did=[]
for i in range(5):
 q={x['arm']:x for x in processes if x['repeat']==i};did.append({'round':i,**{k:(q['maria-sum'][k]-q['pg-sum'][k])-(q['maria-incremental'][k]-q['pg-incremental'][k]) for k in metrics}})
out={'groups':groups,'contrasts':contrasts,'A_gap_reduction':{'rounds':did,'paired_median_ms':{k:s.median(x[k] for x in did) for k in metrics}},'processes':processes};(r/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='processes'},indent=2));print('PASS30 processes/2100 unmodified leaf tests/21 loads and1 reader fork per process')
