from pathlib import Path
import json,gzip,tempfile,shutil,hashlib
from analyze import reduce
p=Path(__file__).parent;names=['records.json','observations.json.gz','owner-summary.json','timing-index.json.gz','inputs.json']
before={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};assert reduce(p)==json.loads((p/'summary.json').read_text());checks=[]
for kind in ['baseline','seed_missing','oracle','early_sql','missing_span','wrong_branch','missing_undo','owner','cleanup']:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)
  for n in names:shutil.copy(p/n,q/n)
  obs=json.loads(gzip.decompress((q/'observations.json.gz').read_bytes()));rs=json.loads((q/'records.json').read_text());r=next(r for r in rs if r['mode']=='fresh' and r['observer']=='on' and r['kind']=='primary');v=obs[r['report']]
  if kind=='baseline':v['prepare_baseline']=False
  elif kind=='seed_missing':v['samples'][0]['spans']=[x for x in v['samples'][0]['spans'] if x['name']!='seed']
  elif kind=='oracle':v['samples'][0]['oracle']=False
  elif kind=='early_sql':next(x for x in v['samples'][0]['spans'] if x['name']=='connect')['begin_ms']=0
  elif kind=='missing_span':v['samples'][0]['traces']['startup']['events']=[x for x in v['samples'][0]['traces']['startup']['events'] if x['name']!='innodb/system_space_open_end']
  elif kind=='wrong_branch':
   next(x for x in v['samples'][0]['traces']['startup']['events'] if x['name']=='innodb/system_space_create_new')['name']='innodb/system_space_existing'
  elif kind=='missing_undo':v['samples'][0]['traces']['startup']['events']=[x for x in v['samples'][0]['traces']['startup']['events'] if x['name']!='innodb/undo_tablespaces_end']
  elif kind=='owner':o=json.loads((q/'owner-summary.json').read_text());o[0]['child_indices'].pop();(q/'owner-summary.json').write_text(json.dumps(o))
  elif kind=='cleanup':v['cleanup_stats']['active_mappings']=1
  if kind in ['missing_span','wrong_branch','missing_undo']:
   # Rebind the mutated trace hash so the intended phase gate, rather than
   # checksum integrity alone, must reject this private negative control.
   index=json.loads(gzip.decompress((q/'timing-index.json.gz').read_bytes()))
   original=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()))[r['report']]['samples'][0]['traces']['startup']
   canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   old=canonical(original);new=canonical(v['samples'][0]['traces']['startup'])
   for meta in index[r['name']].values():
    if meta['canonical_sha256']==old:meta['canonical_sha256']=new
   (q/'timing-index.json.gz').write_bytes(gzip.compress(json.dumps(index).encode()))
  (q/'observations.json.gz').write_bytes(gzip.compress(json.dumps(obs).encode()))
  try:reduce(q)
  except (AssertionError,KeyError):checks.append(kind)
  else:raise AssertionError('missed '+kind)
assert before=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names}
print('PASS: 9 negative controls; original inputs unchanged:',', '.join(checks))
