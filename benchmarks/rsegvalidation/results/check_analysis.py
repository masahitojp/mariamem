from pathlib import Path
import json,gzip,tempfile,shutil,hashlib
from analyze import reduce
p=Path(__file__).parent;names=['records.json','observations.json.gz','owner-summary.json','timing-index.json.gz','inputs.json']
before={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};assert reduce(p)==json.loads((p/'summary.json').read_text());checks=[]
for kind in ['baseline','seed_missing','oracle','early_sql','missing_span','wrong_branch','missing_undo','missing_rseg','double_branch','owner','cleanup','cost_missing','cost_count','cost_overlap','cost_incomplete','header_missing','header_count','header_overlap','header_nested_overlap','header_incomplete','validation_missing','validation_calls','validation_overlap','validation_recovery','validation_crc','validation_bytes','validation_incomplete']:
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
  elif kind in ['missing_rseg','double_branch']:
   r=next(r for r in rs if r['mode']=='fork' and r['kind']=='primary');v=obs[r['report']]
   if kind=='missing_rseg':v['samples'][0]['traces']['startup']['events']=[x for x in v['samples'][0]['traces']['startup']['events'] if x['name']!='innodb/rseg_array_end']
   else:
    ev=v['samples'][0]['traces']['startup']['events'];i=next(i for i,x in enumerate(ev) if x['name'] in ['innodb/undo_empty','innodb/undo_nonempty']);ev.insert(i+1,dict(ev[i],name='innodb/undo_nonempty' if ev[i]['name']=='innodb/undo_empty' else 'innodb/undo_empty'))
  elif kind.startswith('cost_'):
   ev=v['samples'][0]['traces']['startup']['events'];ce=next(x for x in ev if x['name'].startswith('innodb/rseg_cost/'))
   if kind=='cost_missing':ev.remove(ce)
   else:
    cost=json.loads(ce['name'].split('innodb/rseg_cost/',1)[1])
    if kind=='cost_count':cost['null_slots']+=1
    elif kind=='cost_overlap':cost['scan_ns']+=100000000;cost['scan_inclusive_ns']+=100000000
    else:cost['complete']=False
    ce['name']='innodb/rseg_cost/'+json.dumps(cost,separators=(',',':'))
  elif kind.startswith('header_'):
   ev=v['samples'][0]['traces']['startup']['events'];ce=next(x for x in ev if x['name'].startswith('innodb/rseg_cost/'));cost=json.loads(ce['name'].split('innodb/rseg_cost/',1)[1])
   if kind=='header_missing':del cost['header_path']
   elif kind=='header_count':cost['header_path']['hits']+=1
   elif kind=='header_overlap':cost['header_path']['phase_ns'][0]+=100000000;cost['header_path']['total_ns']+=100000000
   elif kind=='header_nested_overlap':cost['header_path']['read_nested_ns'][2]+=100000000
   else:cost['header_path']['incomplete']=1
   ce['name']='innodb/rseg_cost/'+json.dumps(cost,separators=(',',':'))
  elif kind.startswith('validation_'):
   r=next(r for r in rs if r['mode']=='fork' and r['kind']=='primary');v=obs[r['report']]
   ce=next(x for x in v['samples'][0]['traces']['startup']['events'] if x['name'].startswith('innodb/rseg_cost/'));cost=json.loads(ce['name'].split('innodb/rseg_cost/',1)[1]);hp=cost['header_path'];val=hp['validation']
   if kind=='validation_missing':del hp['validation']
   elif kind=='validation_calls':val['calls']+=1
   elif kind=='validation_overlap':val['ns'][0]+=100000000
   elif kind=='validation_recovery':val['counts'][1]=val['recovery_flag']+1
   elif kind=='validation_crc':val['crc_ns']=val['ns'][0]+1
   elif kind=='validation_bytes':val['crc_bytes']=(val['crc_calls']+1)*cost['page_size']
   else:val['incomplete']=1
   ce['name']='innodb/rseg_cost/'+json.dumps(cost,separators=(',',':'))
  elif kind=='owner':o=json.loads((q/'owner-summary.json').read_text());o[0]['child_indices'].pop();(q/'owner-summary.json').write_text(json.dumps(o))
  elif kind=='cleanup':v['cleanup_stats']['active_mappings']=1
  if kind.startswith(('cost_','header_','validation_')) or kind in ['missing_span','wrong_branch','missing_undo','missing_rseg','double_branch']:
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
print('PASS: 27 negative controls; original inputs unchanged:',', '.join(checks))
