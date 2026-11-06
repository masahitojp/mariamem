from pathlib import Path
import json,gzip,copy
from analyze import reduce
import tempfile,shutil,hashlib
p=Path(__file__).parent
files=['records.json','observations.json.gz','owner-summary.json','timings.json.gz','inputs.json']
before={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in files}
assert reduce(p)==json.loads((p/'summary.json').read_text())
checks=[]
for kind in ['early_sql','next_wave_overlap','early_ready','missing_child','cleanup_debt','oracle','owner','clock']:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)
  for n in files:shutil.copy(p/n,q/n)
  obs=json.loads(gzip.decompress((q/'observations.json.gz').read_bytes()));records=json.loads((q/'records.json').read_text())
  r=next(r for r in records if r['arm']=='pages' and r['kind']==('diagnostic' if kind in ['owner','clock'] else 'primary'));v=obs[r['report']]
  if kind=='early_sql':next(z for z in v['samples'][0]['spans'] if z['name']=='connect')['begin_ms']=0
  elif kind=='next_wave_overlap':v['waves'][1]['begin_ms']=0
  elif kind=='early_ready':v['waves'][0]['all_ready_ms']=v['waves'][0]['forks_begin_ms']
  elif kind=='missing_child':v['samples'].pop()
  elif kind=='cleanup_debt':v['cleanup_stats']['active_mappings']=1
  elif kind=='oracle':v['samples'][0]['oracle']=False
  elif kind=='clock':v['samples'][0]['traces']['startup']['epoch_ns']=0
  elif kind=='owner':
   o=json.loads((q/'owner-summary.json').read_text());o[0]['child_indices'].pop();(q/'owner-summary.json').write_text(json.dumps(o))
  (q/'observations.json.gz').write_bytes(gzip.compress(json.dumps(obs).encode()))
  try:reduce(q)
  except (AssertionError,KeyError):checks.append(kind)
  else:raise AssertionError('missed '+kind)
assert before=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in files}
print('PASS: 8 negative controls:',', '.join(checks))
