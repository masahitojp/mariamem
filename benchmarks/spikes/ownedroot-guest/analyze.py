#!/usr/bin/env python3
"""Replay recorded results only; never builds or runs guest code."""
import hashlib,json,statistics
from pathlib import Path
E=Path(__file__).resolve().parent/'evidence'
def read(n):return json.loads((E/n).read_text())
def median(values):return statistics.median(values)
def main():
 files=read('files.json')
 for n,v in files.items():assert hashlib.sha256((E/n).read_bytes()).hexdigest()==v['stored_sha256'],n
 r=read('measurement/receipt.json');assert r['result']=='PASS' and len(r['cells'])==46 and len(r['diagnostics'])==4
 result={'result':'PASS','ordinary_workflows':46,'diagnostic_workflows':4,'groups':[],'paired_total_change_ms':[]}
 for payload,workers in [(0,1),(0,4),(10,1)]:
  group={'payload_mib':payload,'workers':workers};bylabel={}
  for label in ['baseline','candidate']:
   cells=[v for v in r['cells'] if (v['payload_mib'],v['workers'],v['label'])==(payload,workers,label)]
   data=[read('measurement/'+c['name']+'.json') for c in cells];bylabel[label]={c['trial']:d for c,d in zip(cells,data)}
   for c,d in zip(cells,data):
    assert hashlib.sha256((E/'measurement'/(c['name']+'.json')).read_bytes()).hexdigest()==c['result_sha256']
    m=d['final_go']['linear_memory_virtual'];assert m['creates']==m['releases']==5
    assert all(m[k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures'])
   group[label]={'n':len(data),'snapshot_ms':median(next(o['seconds'] for o in d['operations'] if o['name']=='snapshot')*1000 for d in data),'total_ms':median(d['suite_product_seconds']*1000 for d in data),'total_range_ms':[min(d['suite_product_seconds']*1000 for d in data),max(d['suite_product_seconds']*1000 for d in data)],'child_loop_wall_ms':median(d['fork_suite_wall_seconds']*1000 for d in data),'total_alloc_mib':median(d['final_go']['total_alloc_bytes']/2**20 for d in data)}
  group['total_median_change_percent']=(group['candidate']['total_ms']/group['baseline']['total_ms']-1)*100;result['groups'].append(group)
  for i,d in bylabel['baseline'].items():result['paired_total_change_ms'].append({'payload_mib':payload,'workers':workers,'trial':i,'candidate_minus_baseline':(bylabel['candidate'][i]['suite_product_seconds']-d['suite_product_seconds'])*1000})
 for cell in r['diagnostics']:
  if cell['label']!='candidate':continue
  traces=[json.loads(p.read_text()) for p in (E/'measurement'/cell['name']).glob('*.json')]
  capture=next(t for t in traces if t['operation']=='snapshot_capture')
  counts=[v for v in capture['events'] if v['name'].startswith(('root/freeze/','root/acquire/'))]
  assert len(counts)>=8 and all(v.get('bytes_read',0)==0 for v in counts)
  assert any(v.get('bytes_read',0)>0 and v['name'].startswith('root/write/') for v in capture['events'])
 mapped=read('mapped-derived/result.json');assert mapped['result']=='PASS'
 work=mapped['mapped_work'];assert work['root/mapped-source/hash/hash']==work['root/mapped-target/hash/hash']>0
 assert work['root/mapped-copy/mapped/copy']>0
 healthy=read('corruption/healthy.json');corrupt=read('corruption/corrupt.json')
 assert healthy['outcome']=='original_value' and not healthy['injection']['strict_rejected']
 assert corrupt['outcome']=='query_error' and corrupt['injection']['strict_rejected']
 assert corrupt['injection']['metadata_accepted'] and '1877' in corrupt['error']
 result['corruption']={'healthy':healthy['outcome'],'corrupt':corrupt['outcome'],'strict_rejected':True,'metadata_accepted':True}
 regen=read('canonical-regeneration.json');assert regen['result']=='PASS' and len(regen['generated_inventory'])==99
 result['regenerated_files']=99;result['ubuntu']='SKIP: not executed'
 (E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
