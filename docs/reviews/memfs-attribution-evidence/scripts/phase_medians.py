from pathlib import Path
import json,statistics
w=Path(__file__).resolve().parents[1]/'evidence'
a=json.loads((w/'attribution-summary.json').read_text());out=[]
for payload in (0,10):
 for life in ('fresh','fork'):
  group=[r for r in a if r['payload_mib']==payload and r['lifecycle']==life]
  rec=dict(payload_mib=payload,lifecycle=life)
  phases=['fresh_ready_00','fresh_setup_00','child_close_00'] if life=='fresh' else ['prepare_start','prepare_setup','snapshot','fork_ready_00','child_close_00','snapshot_close']
  for phase in phases:
   frames=[p for r in group for p in r['frames'] if p['phase']==phase]
   rec[phase]={key:round(statistics.median(p[key] for p in frames)/1048576,3) for key in ('live_heap_capacity_bytes','live_mapped_logical_bytes','source_heap_logical_bytes','source_unwritten_lower_bytes','source_unwritten_upper_bytes','heap_alloc_bytes','observer_accounted_bytes','observer_bitmap_bytes')}
   for key in ('primary_bytes','rss_bytes'):
    rec[phase][key]=round(statistics.median(next(iter(p['process_counters'].values()))[key] for p in frames)/1048576,3)
  out.append(rec)
(w/'phase-medians.json').write_text(json.dumps(out,indent=2)+'\n')
for r in json.loads((w/'campaign.json').read_text()):
 d=json.loads((w/(r['name']+'.json')).read_text());m=d['go_resource_observation']['after']['linear_memory_virtual']
 assert m['active_mappings']==0 and m['release_failures']==0
print('24-case final mapping cleanup PASS; phase medians regenerated')
