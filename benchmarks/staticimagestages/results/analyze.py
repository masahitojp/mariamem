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
 t=s['traces']['fork'];u=s['traces']['startup'];assert t['operation']=='fork'
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

def reduce(records):
 assert len(records)==12
 expected={(p,r,a) for p in [1,4] for r in range(3) for a in ['anonymous','image']};seen=set();processes=[];children=[]
 for rec in records:
  key=(rec['parallel'],rec['rep'],rec['arm']);assert key in expected and key not in seen;seen.add(key)
  r=rec['report'];assert r['success'] and r['cleanup'] and len(r['samples'])==48
  assert r['resolved_max_forks']==key[0] and 0<r['max_active']<=key[0]
  assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures','grow_failures'])
  assert r['image_after_close']['owned_fds']==0 and r['image_after_close']['closed']
  assert r['image_before_close']['builds']==(1 if key[2]=='image' else 0)
  assert r['image_before_close']['acquires']==(49 if key[2]=='image' else 0)
  assert sorted(x['index'] for x in r['samples'])==list(range(48))
  assert rec['owner']['child_indices']==list(range(48)) and rec['owner']['truncated']==0
  ds=[]
  for sample in r['samples']:
   assert sample['oracle'] and sample['cleanup'] and not sample.get('error')
   d=child(sample,key[2]);ds.append(d);children.append(dict(process=rec['name'],index=sample['index'],lane=sample['lane'],ms=d))
  child_starts={s['traces']['startup']['epoch_ns'] for s in r['samples']};assert len(child_starts)==48
  recorded_starts=[v for v in rec['timing'].values() if v['operation']=='startup'];assert len(recorded_starts)==49
  for sample in r['samples']:
   assert sample['traces']['startup'] in recorded_starts,'child startup file mismatch'
  root=[v for v in rec['timing'].values() if v['epoch_ns'] not in child_starts and any(e['name']=='runtime/memory_begin' for e in v['events']) and v['operation']!='fork']
  assert len(root)==1,(rec['name'],[v['operation'] for v in root]);re=ev(root[0]['events'])
  build=0
  if key[2]=='image':build=re['runtime/image_build_end']-re['runtime/image_build_begin']
  else:assert not any('image_build' in k for k in re)
  processes.append(dict(name=rec['name'],parallel=key[0],rep=key[1],arm=key[2],metrics={k:stats([d[k] for d in ds]) for k in ds[0]},image_build_ms=build,root_start_ms=next(x['end_ms']-x['begin_ms'] for x in r['root_spans'] if x['name']=='root_start'),suite_ms=r['suite_ms'],batch_ms=r['batch_ms']))
 assert seen==expected
 pairs=[];cells=[]
 for p in [1,4]:
  ps=[v for v in processes if v['parallel']==p]
  for rep in range(3):
   a=next(v for v in ps if v['rep']==rep and v['arm']=='anonymous');b=next(v for v in ps if v['rep']==rep and v['arm']=='image')
   pairs.append(dict(parallel=p,rep=rep,delta_p50_ms={k:b['metrics'][k]['p50']-a['metrics'][k]['p50'] for k in a['metrics']},delta_mean_ms={k:b['metrics'][k]['mean']-a['metrics'][k]['mean'] for k in a['metrics']}))
  for arm in ['anonymous','image']:
   rows=[v for v in ps if v['arm']==arm]
   cells.append(dict(parallel=p,arm=arm,median_process_child_p50_ms={k:statistics.median(v['metrics'][k]['p50'] for v in rows) for k in rows[0]['metrics']},median_process_child_p95_ms={k:statistics.median(v['metrics'][k]['p95'] for v in rows) for k in rows[0]['metrics']},over_100ms={k:sum(v['metrics'][k]['over_100ms'] for v in rows) for k in rows[0]['metrics']},image_build_ms=statistics.median(v['image_build_ms'] for v in rows),root_start_ms=statistics.median(v['root_start_ms'] for v in rows)))
 tails=[dict(process=r['name'],child=s['index'],stage=sp['name'],ms=sp['end_ms']-sp['begin_ms']) for r in records for s in r['report']['samples'] for sp in s['spans'] if sp['end_ms']-sp['begin_ms']>100]
 return dict(processes=processes,pairs=pairs,cells=cells,children=children,lifecycle_spans_over_100ms=tails)

if __name__=='__main__':
 p=Path(sys.argv[1]);out=reduce(json.loads(gzip.decompress((p/'observations.json.gz').read_bytes())))
 data=json.dumps(out,indent=2)+'\n'
 if '--check' in sys.argv:assert (p/'summary.json').read_text()==data;print('PASS: read-only replay; 576 partitions, oracles, roots and owners')
 else:(p/'summary.json').write_text(data)
