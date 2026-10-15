"""Summarize paired experiments without mixing resource and plain timing runs."""
import argparse,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
def stats(v):
 return {'n':len(v),'median':statistics.median(v),'min':min(v),'max':max(v)}
def whole(d):return d['workflow_ms_before_validation']+d['times_ms']['baseline/close']
output={}
for campaign in ['plain','resources']:
 records=[json.loads(p.read_text()) for p in sorted((a.evidence/campaign).glob('*/result.json'))]
 out={}
 for rows in [100,10000]:
  group={m:[d for d in records if d['rows']==rows and d['mode']==m] for m in ['e','ce']}
  item={}
  for mode,ds in group.items():
   children=[c for d in ds for c in d['host_reports'][1:]]
   item[mode]={'whole_ms':stats([whole(d) for d in ds]),'snapshot_ms':stats([d['times_ms']['setup/snapshot'] for d in ds]),
    'startup_ms_per_child':stats([d['times_ms'][c+'/startup'] for d in ds for c in ['first','second']]),
    'crud_ms_per_child':stats([d['times_ms'][c+'/crud'] for d in ds for c in ['first','second']]),
    'close_ms_per_child':stats([d['times_ms'][c+'/close'] for d in ds for c in ['first','second']]),
    'copied_mib_per_child':stats([sum(r['Copied'] for r in (c['copies'] or []))/2**20 for c in children]),
    'detach_ms_per_child':stats([sum(r['NS'] for r in (c['copies'] or []))/1e6 for c in children]),
    'copied_files_per_child':stats([len(c['copies'] or []) for c in children]),
    'baseline_bytes':stats([sum(v.get('bytes',0) for v in d['baseline_manifest']['entries'].values()) for d in ds])}
   if campaign=='resources':
    for role,hosts in [('setup',[d['host_reports'][0] for d in ds]),('child',children)]:
     item[mode][role]={k:stats([c[k]/(2**20 if k!='num_gc' else 1) for c in hosts]) for k in ['maxrss_raw','total_alloc_bytes','heap_alloc_bytes','heap_sys_bytes','num_gc']}
  pairs=[{'repeat':d['repeat'],'e_ms':whole(d),'ce_ms':whole(next(x for x in group['ce'] if x['repeat']==d['repeat']))} for d in group['e']]
  for d in pairs:d['delta_ms']=d['ce_ms']-d['e_ms'];d['delta_percent']=100*d['delta_ms']/d['e_ms']
  item['pairs']=pairs;item['paired_delta_ms']=stats([d['delta_ms'] for d in pairs]);item['ce_slower_pairs']=sum(d['delta_ms']>0 for d in pairs)
  out[str(rows)]=item
 output[campaign]=out
(a.evidence/'summary.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
