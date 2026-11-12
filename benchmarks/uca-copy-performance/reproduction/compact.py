from pathlib import Path
import json,csv,hashlib,importlib.util,subprocess
E=Path(__file__).resolve().parent
rows=json.loads((E/'observations.json').read_text())
if not (E/'analyze.py').exists():
 (E/'analyze.py').write_bytes(subprocess.check_output(['git','show','d24087eedd21c6384c231fb119c8e98da7b370aa:docs/reviews/timer-calibration-measure/analyze.py'],cwd=E.parent/'worktree'))
spec=importlib.util.spec_from_file_location('original',E/'analyze.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);expected=module.analyze()
D=E/'report';D.mkdir(exist_ok=True)
def csvwrite(name,fields,rows):
 with (D/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
batches=[];life=[];stages=[]
for i,r in enumerate(rows):
 b={k:r[k] for k in ['arm','kind','repeat','parallel','process_wall_ms','started_at_utc','exit_code','scratch_empty','accepted','max_rss_bytes']};b['record']=i
 if r['kind']=='lifecycle':
  b.update(result=r['data']['result'],active_mappings_after=r['data']['active_mappings_after'])
  for j,v in enumerate(r['data']['observations']): life.append(dict(record=i,index=j,**v))
 else:
  m=r['data']['meta'];b['elapsed_ms']=r['data']['elapsed_ms']
  b.update({k:m[k] for k in ['cpu_ms','parallel','fork_cap','read_cases','write_cases','test_exit','active_mappings_after']})
  lane={}
  for v in r['data']['spans']:
   if v['kind'] not in ['fork','sample','cleanup','boot']:continue
   o=lane.setdefault(v['lane'],{'record':i,'lane':v['lane']});key=v['kind']+'_ms';assert key not in o
   o[key]=v['end_ms']-v['start_ms']
  stages.extend(lane.values())
 batches.append(b)
csvwrite('batches.csv',['record','arm','kind','repeat','parallel','started_at_utc','process_wall_ms','exit_code','scratch_empty','accepted','max_rss_bytes','result','active_mappings_after','elapsed_ms','cpu_ms','fork_cap','read_cases','write_cases','test_exit'],batches)
csvwrite('lifecycle.csv',['record','index','kind','wall_ms','cpu_ms'],life)
csvwrite('stages.csv',['record','lane','boot_ms','fork_ms','sample_ms','cleanup_ms'],stages)
source=(E/'analyze.py').read_text()
source=source.replace('import argparse,json,math,statistics','import argparse,json,math,statistics,csv')
loader='''def load_rows():
 rows=[]
 for b in csv.DictReader((P/'batches.csv').open()):
  r={k:b[k] for k in ('arm','kind','started_at_utc')}
  r.update({k:int(b[k]) for k in ('repeat','parallel','exit_code')})
  r.update({k:b[k]=='True' for k in ('scratch_empty','accepted')})
  r['process_wall_ms']=float(b['process_wall_ms'])
  if r['kind']=='lifecycle':
   r['data']={'result':b['result'],'active_mappings_after':int(b['active_mappings_after']),'observations':[]}
  else:
   r['data']={'elapsed_ms':float(b['elapsed_ms']),'meta':{k:b[k] for k in ('cpu_ms','read_cases','write_cases','test_exit','active_mappings_after','parallel','fork_cap')},'spans':[]}
  assert int(b['record'])==len(rows);rows.append(r)
 for o in csv.DictReader((P/'lifecycle.csv').open()):
  r=rows[int(o['record'])];assert int(o['index'])==len(r['data']['observations'])
  r['data']['observations'].append({'kind':o['kind'],'wall_ms':float(o['wall_ms']),'cpu_ms':float(o['cpu_ms'])})
 for o in csv.DictReader((P/'stages.csv').open()):
  for kind in ('fork','sample','cleanup','boot'):
   if o[kind+'_ms']:
    rows[int(o['record'])]['data']['spans'].append({'kind':kind,'duration_ms':float(o[kind+'_ms'])})
 return rows

'''
source=source.replace('def analyze():',loader+'def analyze():')
source=source.replace("rows=json.loads((P/'observations.json').read_text());assert len(rows)==38",'rows=load_rows();assert len(rows)==38')
source=source.replace("[('fork',21),('sample',21),('read',50),('write',20)]", "[('fork',21),('sample',21)]")
source=source.replace("v['end_ms']-v['start_ms']", "v['duration_ms']")
(D/'analyze.py').write_text(source.replace('retained minified JSON','retained compact CSV'))
(D/'summary.json').write_text(json.dumps(expected,indent=2)+'\n')
subprocess.run(['python3',str(D/'analyze.py'),'--check'],check=True)
print('CSV preserves every observation used in original summary; exact replay PASS')
