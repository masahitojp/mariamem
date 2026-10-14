from pathlib import Path
from collections import defaultdict
import json,statistics

w=Path(__file__).resolve().parents[1];e=w/'evidence'
records=json.loads((e/'campaign.json').read_text())
summary=[];attribution=[]
def category(path):
 if path.startswith('snapshot-out/'):return 'snapshot-copy'
 name=path.rsplit('/',1)[-1]
 if name.startswith('ib_logfile') or path.startswith('mariadb/#innodb_redo'):return 'redo'
 if name.startswith('ibtmp'):return 'temporary-tablespace'
 if name.startswith('ibdata'):return 'system-tablespace'
 if name.endswith('.ibd'):return 'table-tablespace'
 return 'other'
for payload,tables in ((0,1),(10,8)):
 for lifecycle in ('fresh','fork'):
  group=[r for r in records if (r['payload_mib'],r['tables'],r['lifecycle'])==(payload,tables,lifecycle)]
  row=dict(payload_mib=payload,tables=tables,lifecycle=lifecycle)
  for mode in ('control','observed'):
   samples=[r for r in group if r['mode']==mode]
   row[mode]={k:dict(median=statistics.median(r[k] for r in samples),min=min(r[k] for r in samples),max=max(r[k] for r in samples)) for k in ('suite_product_seconds','suite_cpu_seconds','peak_rss_bytes','cumulative_alloc_bytes')}
  row['observed_wall_change_pct']=(row['observed']['suite_product_seconds']['median']/row['control']['suite_product_seconds']['median']-1)*100
  summary.append(row)
for r in records:
 if r['mode']!='observed' or r['returncode']!=0:continue
 d=json.loads((e/(r['name']+'-audit.json')).read_text());totals=defaultdict(lambda:defaultdict(int));byfile=[]
 for n in d['nodes']:
  f=dict(id=n['id'],fs=n['fs'],role=n['role'],path=n['path'],category=category(n['path']),max_logical_bytes=n['max_logical_bytes'],max_capacity_bytes=n['max_capacity_bytes'],imported_bytes=n['imported_bytes'],epochs=n['epoch'],phase_operation_stats=n['phase_operation_stats'])
  byfile.append(f)
  for phase,stats in n['phase_operation_stats'].items():
   key=n['role']+'|'+phase+'|'+category(n['path'])
   for name,value in stats.items():totals[key][name]+=value
 frames=[]
 for frame in d['frames']:
  rows=[n for n in frame['nodes'] if not n['fs_ended'] and (n['linked'] or n['open_handles']>0)]
  sources=[n for n in rows if n['role']=='fresh' and not n['mapped'] and n['imported_bytes']==0 and not n['path'].startswith('snapshot-out/')]
  heaps=[n for n in rows if not n['mapped']]
  point=dict(phase=frame['phase'],live_heap_logical_bytes=sum(n['logical_bytes'] for n in heaps),live_heap_capacity_bytes=sum(n['capacity_bytes'] for n in heaps),live_mapped_logical_bytes=sum(n['logical_bytes'] for n in rows if n['mapped']),source_heap_logical_bytes=sum(n['logical_bytes'] for n in sources),source_heap_capacity_bytes=sum(n['capacity_bytes'] for n in sources),source_unwritten_lower_bytes=sum(n['logical_bytes']-n['written_upper_bytes'] for n in sources),source_unwritten_upper_bytes=sum(n['logical_bytes']-n['written_lower_bytes'] for n in sources),source_spare_capacity_bytes=sum(n['capacity_bytes']-n['logical_bytes'] for n in sources),observer_accounted_bytes=frame['observer_accounted_bytes'],observer_bitmap_bytes=frame['observer_bitmap_bytes'],heap_alloc_bytes=frame['heap_alloc_bytes'],total_alloc_bytes=frame['total_alloc_bytes'],num_gc=frame['num_gc'],process_counters=frame.get('process_counters'),files=sources)
  frames.append(point)
 attribution.append(dict(name=r['name'],**{k:r[k] for k in ('payload_mib','tables','lifecycle','trial')},totals={k:dict(v) for k,v in totals.items()},files=byfile,frames=frames,observer_accounted_bytes=d['observer_accounted_bytes'],observer_bitmap_bytes=d['observer_bitmap_bytes']))
(e/'comparison-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(e/'attribution-summary.json').write_text(json.dumps(attribution,indent=2)+'\n')
for r in summary:print(r['payload_mib'],r['lifecycle'],'observer wall%',round(r['observed_wall_change_pct'],1))
for r in attribution:
 initial=realloc=copy=detached=0
 for v in r['totals'].values():initial+=v['initial_capacity_bytes'];realloc+=v['realloc_capacity_bytes'];copy+=v['old_logical_copied_bytes'];detached+=v['mapped_detach_copied_bytes']
 print(r['name'],'MiB initial/realloc/copy/detach',*(round(v/2**20,2) for v in (initial,realloc,copy,detached)))
 if r['trial']==0:
  for p in r['frames']:
   if 'ready' in p['phase'] or 'setup' in p['phase'] or p['phase']=='snapshot':
    print(' ',p['phase'],'heap cap',round(p['live_heap_capacity_bytes']/2**20,2),'source len',round(p['source_heap_logical_bytes']/2**20,2),'unwritten bounds',round(p['source_unwritten_lower_bytes']/2**20,2),round(p['source_unwritten_upper_bytes']/2**20,2),'spare',round(p['source_spare_capacity_bytes']/2**20,2))
