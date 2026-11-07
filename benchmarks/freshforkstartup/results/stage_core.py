"""Retained-data-only stage attribution. --check is read only."""
import json, statistics, math, sys, gzip
from pathlib import Path
PARTS=['before_memory','factory_lock_wait','map_and_protect','module_init','memory_other','handoff','execute_to_ready','ready_handling','diagnostic_finish']
def stats(xs):
 s=sorted(xs)
 return dict(n=len(s),p50=statistics.median(s),p95=s[math.ceil(.95*len(s))-1],mean=statistics.mean(s),max=max(s),over_100ms=sum(x>100 for x in s))
def ev(xs):
 d={x['name']:x['offset_ns']/1e6 for x in xs};assert len(d)==len(xs),'duplicate event'
 return d

def child(s,arm):
 t=s['traces'].get('fork',s['traces']['api_startup']);u=s['traces']['startup'];assert t['operation'] in ['fork','api_startup']
 shift=(u['epoch_ns']-t['epoch_ns'])/1e6;assert shift>=0
 e=ev(t['events']);e.update({k:v+shift for k,v in ev(u['events']).items() if k not in ['begin','end']});spans={x['name']:x['end_ms']-x['begin_ms'] for x in s['spans']};total=spans['start_or_fork']
 ordered=['begin','runtime/memory_begin','runtime/map_begin','runtime/map_end','runtime/module_begin','runtime/module_end','runtime/memory_ready','runtime/guest_execute_begin','ready_frame_decoded','end']
 assert all(e[a]<=e[b] for a,b in zip(ordered,ordered[1:])),e
 assert not any('image_build' in k for k in e),'image rebuild during Fork'
 def delta(a,b):return e[b]-e[a]
 lock=0
 if arm=='image':
  assert e['runtime/memory_begin']<=e['runtime/image_lock_begin']<=e['runtime/image_lock_acquired']<=e['runtime/map_begin']
  lock=delta('runtime/image_lock_begin','runtime/image_lock_acquired')
 else:assert not any('image_lock' in k for k in e)
 d=dict(before_memory=e['runtime/memory_begin'],factory_lock_wait=lock,map_and_protect=delta('runtime/map_begin','runtime/map_end'),module_init=delta('runtime/module_begin','runtime/module_end'),handoff=delta('runtime/memory_ready','runtime/guest_execute_begin'),execute_to_ready=delta('runtime/guest_execute_begin','ready_frame_decoded'),ready_handling=delta('ready_frame_decoded','end'),diagnostic_finish=total-e['end'])
 d['memory_other']=delta('runtime/memory_begin','runtime/memory_ready')-lock-d['map_and_protect']-d['module_init']
 assert all(v>=0 for v in d.values()),d
 assert abs(sum(d.values())-total)<1e-6,'partition does not reconcile'
 d['fork_total']=total
 # Nested guest phases are reported separately; never added to the partition.
 g=ev(u['guest']['events'])
 for key,a,b in [('guest_server_init','server_init_begin','server_init_complete'),('guest_routine_schema','server_init_complete','routine_schema_complete')]:
  d[key]=g[b]-g[a];assert d[key]>=0
 d['first_select']=next(x['end_ms'] for x in s['spans'] if x['name']=='select1')-next(x['begin_ms'] for x in s['spans'] if x['name']=='start_or_fork')
 return d
