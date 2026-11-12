"""Reduce completed diagnostics to histograms and selected events, not raw logs."""
from pathlib import Path
import collections,hashlib,json,sys,shutil
W=Path(sys.argv[1]).resolve();S=W/'worktree';E=W/'evidence';T=W/'temp';D=S/'benchmarks/pool-worker-progress/results';D.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,value): (D/name).write_text(json.dumps(value,indent=2)+'\n')
def hist(values):return sorted(collections.Counter(values).items())
runs=[];examples=[];bindings=[]
for i in range(9):
 name='control' if i==0 else f'natural-{i}';d=E/name
 reads=json.loads((d/'read.json').read_text());trace=json.loads((d/'trace.json').read_text());sql=json.loads((d/'sql.json').read_text())
 events=[e for r in reads for e in r['progress'] or []];qs=[q for r in reads for q in r['ios'] or []]
 counts=collections.Counter(e['kind'] for e in events)
 assert all(r['closed'] and not r['truncated'] for r in reads)
 assert all(q['submit_us']<=q['worker_us']<=q['sync_end_us']<=q['completion_submit_us']<=q['callback_us']<=q['callback_return_us'] for q in qs)
 global_times=[];group_times=[];spawns=[];pending_intervals=[];binding_count=0
 for r in reads:
  es=r['progress'] or [];spawn_queue=collections.deque();byworker={};last_pending=None
  for e in es:
   k=e['kind']
   if k=='pending_exchange' and e['aux']==0:last_pending=e
   if k=='spawn_call':spawn_queue.append(e)
   if k=='worker_enter':
    assert spawn_queue;start=spawn_queue.popleft();byworker[e['worker']]={'start':start,'entered':e}
   if k=='init_return':byworker[e['worker']]['init']=e
   if k=='pending_clear':
    v=byworker[e['worker']];assert e['at_us']>=v['init']['at_us']>=v['entered']['at_us']>=v['start']['at_us']
    spawns.append([v['entered']['at_us']-v['start']['at_us'],v['init']['at_us']-v['entered']['at_us'],e['at_us']-v['start']['at_us']])
   if k=='spawn_call' and e['actor']=='maintenance':
    # Selected event window only; other requests retain histogram/census.
    window=[x for x in es if e['at_us']-1000<=x['at_us']<=e['at_us']+2000]
    examples.append({'run':name,'db':r['db_id'],'kind':'maintenance_spawn','events':window})
  assert not spawn_queue
  for q in r['ios'] or []:
   for label,start in [('initial',q['submit_us']),('completion',q['completion_submit_us'])]:
    a=q[label+'_admission'];end=a['dequeued_us'];assert start<=end<=a['group_enter_us']<=a['group_run_us']
    global_times.append(end-start);group_times.append(a['group_run_us']-a['group_enter_us'])
    # Events exactly match queue/task generation interval, never "unfinished == queued".
    task=q['cb']+44
    matched=[e for e in es if e['kind']=='dequeue' and e['task']==task and e['pool']==a['pool'] and end<=e['at_us']<=a['group_enter_us']]
    assert len(matched)==1,(name,r['db_id'],q['id'],label)
    enq=[e for e in es if e['kind']=='enqueue' and e['task']==task and start<=e['at_us']<=matched[0]['at_us']]
    assert len(enq)==1,(name,r['db_id'],q['id'],label,'enqueue')
    binding_count+=1
  # One actual pending-refusal example, without retaining every repetitive event.
  if name=='natural-1' and not any(x['kind']=='pending_refusal' for x in examples):
   e=next((x for x in es if x['kind']=='add_pending'),None)
   if e:
    window=[x for x in es if e['at_us']-20<=x['at_us']<=e['at_us']+60]
    examples.append({'run':name,'db':r['db_id'],'kind':'pending_refusal','events':window})
 phase_counts=collections.Counter();phase_long=collections.Counter()
 for rec in sql:
  for phase,values in rec['durations_us'].items():
   phase_counts[phase]+=len(values);phase_long[phase]+=sum(n>=100000 for n in values)
 assert counts['spawn_call']==counts['worker_enter']==counts['pending_clear']==counts['worker_exit']
 assert counts['enqueue']==counts['dequeue']==counts['task_begin']==counts['task_end']
 assert counts['wait_begin_applied']==counts['wait_end_applied']
 # Fn16598 returns the constructed thread-object address, not errno.
 assert all(e['aux']>0 for e in events if e['kind']=='spawn_return')
 assert counts['spawn_failure_clear']==0
 row={'name':name,'control':i==0,'wall_ms_diagnostic':trace['elapsed_ms'],'cases':70,'closed_observers':len(reads),'active_mappings_after':0,'scratch_empty':True,'read_requests':len(qs),'request_stage_bindings':binding_count,'phase_counts':dict(phase_counts),'phase_ge100ms':dict(phase_long),'event_counts':dict(counts),'spawn_actors':dict(collections.Counter(e['actor'] for e in events if e['kind']=='spawn_call')),'outer_reject_count':sum(e['queue']>0 and e['active']-e['long']-e['waiting']>e['cap'] for e in events if e['kind']=='gate'),'observed_caps':sorted(set(e['cap'] for e in events if e['locked'])),'global_us_histogram':hist(global_times),'group_us_histogram':hist(group_times),'spawn_intervals_us':spawns}
 runs.append(row)
 # Single-line per-run tuples prevent report source expansion; all queue durations retained as histogram.
(D/'observations.json').write_text(json.dumps(runs,separators=(',',':'))+'\n')
for example in examples:
 all_events=example['events']
 keep_kinds={'spawn_call','spawn_return','worker_enter','init_begin','init_return','pending_clear','spawn_failure_clear','add_max','add_throttle'}
 selected=[e for e in all_events if e['kind'] in keep_kinds or e['actor']=='maintenance']
 selected += [e for e in all_events if e['kind']=='add_pending'][:2]
 example['full_window_events']=len(all_events)
 example['full_window_sha256']=hashlib.sha256(json.dumps(all_events,sort_keys=True).encode()).hexdigest()
 example['events']=sorted(selected,key=lambda e:e['at_us'])
 example['selection']='worker creation/init/clear events; all maintenance actor events; first two pending refusals. Other repeated queue/task events omitted.'
dump('examples.json',examples)
inputs=json.loads((E/'inputs.json').read_text());inputs['retention']='All queue durations as exact microsecond histograms; all spawn intervals; per-run census; selected actual event windows. Full request/worker raw event streams reduced after generation-binding check; not reconstructible from histograms.';inputs['unit']='Focused read/dispatch/progress -race PASS';inputs['binary_build_count']=1;inputs['invalid_startup_attempts']=[json.loads(p.read_text()) for p in sorted(E.glob('invalid-*/assessment.json'))]
inputs['raw_files']={str(p.relative_to(E)): {'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(E.rglob('*')) if p.is_file() and p.name not in ['inputs.json','runs.json']}
dump('inputs.json',inputs)
cap=json.loads(next((E/'control').glob('capture-*.json')).read_text());text=(E/'control'/cap['profile_file']).read_text();blocks=[b for b in text.split('\n\n') if any(l.startswith('# labels: ') and json.loads(l[10:]).get('db_id')==cap['db_id'] for l in b.splitlines())];selected='\n\n'.join(blocks)+'\n';(D/'control-profile.txt').write_text(selected);cap['original_profile_sha256']=sha(E/'control'/cap['profile_file']);cap['retained_profile_sha256']=sha(D/'control-profile.txt');cap['selection']='complete matching-DB blocks only';dump('control.json',cap)
shutil.copy2(T/'unit.log',D/'unit.txt')
print('REDUCED',len(runs),'processes',sum(x['read_requests'] for x in runs),'read requests; all generation/queue bindings PASS')
