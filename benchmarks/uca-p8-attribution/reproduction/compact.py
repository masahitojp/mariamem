from pathlib import Path
import csv,json,hashlib,shutil,subprocess
E=Path(__file__).resolve().parent;rows=json.loads((E/'observations.json').read_text());D=E/'report';D.mkdir(exist_ok=True)
bs=[];cs=[];ph=[];long=[];caps=[]
for r in rows:
 b={k:r[k] for k in ['name','mode','arm','repeat','rss_bytes','exit_code','scratch_empty','accepted']};b.update(suite_ms=r['trace']['elapsed_ms'],cpu_ms=r['trace']['meta']['cpu_ms'],active_mappings_after=r['trace']['meta']['active_mappings_after']);bs.append(b)
 lanes={}
 for span in r['trace']['spans']:
  if span['kind'] not in ['fork','sample','cleanup'] or span['lane']=='setup':continue
  c=lanes.setdefault(span['lane'],{'name':r['name'],'lane':span['lane']})
  key=span['kind']+'_ms';assert key not in c;c[key]=span['end_ms']-span['start_ms']
 cs+=list(lanes.values())
 for rec in r.get('loaders',[]):
  for phase,vals in rec['durations_us'].items():ph.append({'name':r['name'],'db_id':rec['db_id'],'lane':rec['lane'],'phase':phase,'count':len(vals),'total_ms':sum(vals)/1000,'max_ms':max(vals)/1000,'gt100':sum(x>100000 for x in vals)})
  for op in rec.get('operations_ge50ms') or []:long.append({'name':r['name'],'db_id':rec['db_id'],'lane':rec['lane'],**op})
 for cap in r['captures']:
  caps.append({'name':r['name'],'mode':r['mode'],'arm':r['arm'],**cap})
  if cap.get('retained_profile'):
   pp=D/cap['retained_profile'];raw=(E/cap['retained_profile']).read_text();selected=[]
   for block in raw.split('\n\n'):
    labels=next((json.loads(line[len('# labels: '):]) for line in block.splitlines() if line.startswith('# labels: ')),{})
    if labels.get('db_id')==cap['db_id']:selected.append(block)
   assert len(selected)==cap['matching_db_blocks']
   pp.write_text('# Selected matching-DB blocks; original profile hash retained in captures.json\n\n'+'\n\n'.join(selected)+'\n')
   caps[-1]['retained_profile_sha256']=hashlib.sha256(pp.read_bytes()).hexdigest()
   caps[-1]['selection']='Only complete matching db_id blocks; unrelated DB/runtime blocks omitted; original bytes/hash/truncation and capture window remain unchanged.' 
def write(name,fields,rows):
 with (D/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
write('batches.csv',['name','mode','arm','repeat','suite_ms','cpu_ms','rss_bytes','exit_code','scratch_empty','accepted','active_mappings_after'],bs)
write('children.csv',['name','lane','fork_ms','sample_ms','cleanup_ms'],cs)
write('phases.csv',['name','db_id','lane','phase','count','total_ms','max_ms','gt100'],ph)
write('long-operations.csv',['name','db_id','lane','phase','order_id','product_id','begin_us','duration_us','error'],long)
(D/'captures.json').write_text(json.dumps(caps,indent=2)+'\n')
shutil.copy2(E/'analyze.py',D/'analyze.py');subprocess.run(['python3',D/'analyze.py'],check=True)
subprocess.run(['python3',D/'analyze.py','--check'],check=True)
