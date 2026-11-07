from pathlib import Path
import json,gzip,tempfile,shutil,hashlib
from analyze import reduce
p=Path(__file__).parent;names=['records.json','observations.json.gz','owner-summary.json','timing-index.json.gz','inputs.json'];before={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};assert reduce(p)==json.loads((p/'summary.json').read_text());checks=[]
for kind in ['baseline','oracle','cleanup','owner','wave','seed','arm','observer','cpu','crc_missing','crc_bytes','crc_count','crc_overlap','recovery','incomplete']:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)
  for n in names:shutil.copy2(p/n,q/n)
  rs=json.loads((q/'records.json').read_text());obs=json.loads(gzip.decompress((q/'observations.json.gz').read_bytes()));r=next(x for x in rs if x['mode']=='fresh' and x['kind']=='primary');v=obs[r['report']]
  if kind=='baseline':v['prepare_baseline']=False
  elif kind=='oracle':v['samples'][0]['oracle']=False
  elif kind=='cleanup':v['cleanup_stats']['active_mappings']=1
  elif kind=='owner':o=json.loads((q/'owner-summary.json').read_text());o[0]['child_indices'].pop();(q/'owner-summary.json').write_text(json.dumps(o))
  elif kind=='wave':v['waves'][0]['all_ready_ms']=0
  elif kind=='seed':v['samples'][0]['spans']=[x for x in v['samples'][0]['spans'] if x['name']!='seed']
  elif kind=='arm':r['arm']='unknown';(q/'records.json').write_text(json.dumps(rs))
  elif kind=='observer':r['observer']='on';(q/'records.json').write_text(json.dumps(rs))
  elif kind=='cpu':v['samples'][0]['fork_cpu_ms']=-1
  else:
   r=next(x for x in rs if x['kind']=='diagnostic');v=obs[r['report']];tr=v['samples'][0]['traces']['startup'];h=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();old=h(tr)
   ce=next(x for x in tr['events'] if x['name'].startswith('innodb/rseg_cost/'));cost=json.loads(ce['name'].split('innodb/rseg_cost/',1)[1]);val=cost['header_path']['validation']
   if kind=='crc_missing':del cost['header_path']['validation']
   elif kind=='crc_bytes':val['crc_bytes']+=1
   elif kind=='crc_count':val['crc_calls']-=1
   elif kind=='crc_overlap':val['crc_ns']=val['ns'][0]+1
   elif kind=='recovery':val['recovery_flag']=0
   else:val['incomplete']=1
   ce['name']='innodb/rseg_cost/'+json.dumps(cost,separators=(',',':'));new=h(tr);idx=json.loads(gzip.decompress((q/'timing-index.json.gz').read_bytes()))
   for meta in idx[r['name']].values():
    if meta['canonical_sha256']==old:meta['canonical_sha256']=new
   (q/'timing-index.json.gz').write_bytes(gzip.compress(json.dumps(idx).encode()))
  (q/'observations.json.gz').write_bytes(gzip.compress(json.dumps(obs).encode()))
  try:reduce(q)
  except (AssertionError,KeyError):checks.append(kind)
  else:raise AssertionError('missed '+kind)
assert before=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};print('PASS',len(checks),'mutations; original inputs unchanged',checks)
