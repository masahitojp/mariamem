from pathlib import Path
import json,gzip,tempfile,shutil,hashlib
from analyze import reduce
p=Path(__file__).parent;names=['records.json','observations.json.gz','owner-summary.json','timing-index.json.gz','inputs.json','plan.json'];before={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};assert reduce(p)==json.loads((p/'summary.json').read_text());checks=[]
for kind in ['baseline','oracle','cleanup','owner','wave','seed','arm','observer','cpu','mode','counter_missing','counter_negative','counter_fast','counter_global','positive_control','order','stage_missing']:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)
  for n in names:shutil.copy2(p/n,q/n)
  rs=json.loads((q/'records.json').read_text());obs=json.loads(gzip.decompress((q/'observations.json.gz').read_bytes()));owners=json.loads((q/'owner-summary.json').read_text());r=next(x for x in rs if x['kind']=='primary');v=obs[r['report']]
  if kind=='baseline':v['prepare_baseline']=False
  elif kind=='oracle':v['samples'][0]['oracle']=False
  elif kind=='cleanup':v['cleanup_stats']['active_mappings']=1
  elif kind=='owner':owners[0]['child_indices'].pop()
  elif kind=='wave':v['waves'][0]['all_ready_ms']=0
  elif kind=='seed':v['samples'][0]['spans']=[x for x in v['samples'][0]['spans'] if x['name']!='seed']
  elif kind=='arm':r['arm']='unknown'
  elif kind=='observer':r['observer']='on'
  elif kind=='cpu':v['samples'][0]['fork_cpu_ms']=-1
  elif kind=='mode':v['crc']['fast_enabled']=1-v['crc']['fast_enabled']
  elif kind=='counter_missing':del v['crc']
  elif kind=='counter_negative':v['crc']['crc_bytes']=-1
  elif kind=='counter_fast':v['crc']['fast_calls']=v['crc']['crc_calls']+1
  elif kind=='counter_global':next(x for x in owners if x['name']==r['name'])['crc_children'][0]['validator_calls']=v['crc']['validator_calls']+1
  elif kind=='positive_control':
   r=next(x for x in rs if x['kind']=='positive');next(x for x in owners if x['name']==r['name'])['crc_children'][0].update(crc_calls=0,fast_calls=0,crc_bytes=0)
  elif kind=='order':
   pl=json.loads((q/'plan.json').read_text());pl['primary_order'].reverse();(q/'plan.json').write_text(json.dumps(pl))
  elif kind=='stage_missing':
   r=next(x for x in rs if x['kind']=='diagnostic');v=obs[r['report']];tr=v['samples'][0]['traces']['startup'];h=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();old=h(tr)
   tr['guest']['initialization']['events']=[x for x in tr['guest']['initialization']['events'] if x['name']!='buffer_pool_complete'];new=h(tr);idx=json.loads(gzip.decompress((q/'timing-index.json.gz').read_bytes()))
   for meta in idx[r['name']].values():
    if meta['canonical_sha256']==old:meta['canonical_sha256']=new
   (q/'timing-index.json.gz').write_bytes(gzip.compress(json.dumps(idx).encode()))
  (q/'records.json').write_text(json.dumps(rs));(q/'owner-summary.json').write_text(json.dumps(owners));(q/'observations.json.gz').write_bytes(gzip.compress(json.dumps(obs).encode()))
  try:reduce(q)
  except (AssertionError,KeyError):checks.append(kind)
  else:raise AssertionError('missed '+kind)
assert before=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};print('PASS',len(checks),'mutations; original inputs unchanged',checks)
