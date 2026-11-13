from pathlib import Path
import json,statistics as s
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==24 and all(x['returncode']==0 and x['leaf_pass']==70 for x in rows);processes=[];arms=['pg-official','pg-matched','maria-of','maria-matched']
for x in rows:
 t=json.loads((r/f'{x["arm"]}-{x["repeat"]}-trace.json').read_text());assert sum(v['name']=='test' for v in t['spans'])==70;assert sum(v['name']=='sample' for v in t['spans'])==21
 a={**x,'elapsed_ms':t['elapsed_ms']}
 for phase in ['sample','test','import','snapshot','boot']:
  a[phase+'_ms']=s.median(v['end_ms']-v['start_ms'] for v in t['spans'] if v['name']==phase)
 reader=[v for v in t['spans'] if v['name']=='reader_fork'];want=0 if x['arm']=='pg-official' else 1;assert len(reader)==want;a['reader_fork_ms']=sum(v['end_ms']-v['start_ms'] for v in reader);processes.append(a)
groups={}
for arm in arms:
 a=[x for x in processes if x['arm']==arm and x['repeat']>=0];assert len(a)==5;groups[arm]={k:s.median(x[k] for x in a) for k in ['wall_ms','cpu_ms','sample_ms','test_ms','elapsed_ms','import_ms','snapshot_ms','boot_ms','reader_fork_ms']};groups[arm]['sample_range_ms']=[min(x['sample_ms'] for x in a),max(x['sample_ms'] for x in a)]
contrasts={}
for target,base in [('pg-matched','pg-official'),('maria-matched','maria-of'),('maria-matched','pg-matched')]:
 a=[]
 for i in range(5):
  q={x['arm']:x for x in processes if x['repeat']==i};a.append({'round':i,**{k:q[target][k]-q[base][k] for k in ['wall_ms','cpu_ms','sample_ms','test_ms']}})
 contrasts[target+' minus '+base]={'rounds':a,'paired_median_ms':{k:s.median(x[k] for x in a) for k in a[0] if k!='round'}}
out={'groups':groups,'contrasts':contrasts,'processes':processes};(r/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='processes'},indent=2));print('PASS24 processes/1680 leaf tests/21 loads per process/reader_fork counts')
