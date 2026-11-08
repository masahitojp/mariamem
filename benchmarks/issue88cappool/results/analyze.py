"""Read-only replay of a finite, same-binary read1/read4 comparison."""
from pathlib import Path
import json,hashlib,statistics,math,sys,copy,re
HERE=Path(__file__).resolve().parent

def dist(values):
 if not values:return None
 s=sorted(values)
 def q(p):return s[max(0,math.ceil(len(s)*p)-1)]
 return dict(n=len(s),p50_ms=round(statistics.median(s),3),p95_ms=round(q(.95),3),p99_ms=round(q(.99),3),max_ms=round(s[-1],3),ge100ms=sum(v>=100 for v in s))

def analyze(obs):
 assert len(obs)==25
 runs=[];casecount=0;closed=0
 for r in obs:
  m=r['trace']['meta'];arm=r['read_threads'];on=r['watcher']
  assert arm==1 and m['innodb_read_io_threads']==str(arm) and m['innodb_buffer_pool_size']==m['innodb_buffer_pool_size_max']==str(r['pool_mib']*2**20)
  assert m['test_exit']=='0' and m['active_mappings_after']=='0' and m['read_cases']=='50' and m['write_cases']=='20';casecount+=70
  assert len(r['loaders'])==21 and not r['read_truncated']
  assert len(r['read_observers'])==(22 if on else 0)
  assert r['pool_mib'] in (16,8) and r['variant']==str(r['pool_mib']) and r['startup_cap']=='normal'
  events=r['cap_events'];assert events
  assert len(events)<=128 and all(v['requested']==1 and v['phase'] in ('load','recovery') and v['pool'] and v['db_id'] for v in events)
  assert all(v['selected']==0 for v in events)
  assert all(1<=v['resolved']<=v['max'] and v['resolved']>=v['min'] for v in events)
  assert all(v['resolved']==16 for v in events)
  assert {v['db_id'] for v in events}=={f'issue68-db-{i}' for i in range(2,23)}
  assert len(events)==42 and all(sum(v['db_id']==db and v['phase']==phase for v in events)==1 for db in {v['db_id'] for v in events} for phase in ('load','recovery'))
  timers=[]
  for reader in r['read_observers']:
   assert reader['closed'] and not reader['truncated'];closed+=1
   rows=reader['timing_census'];assert len(rows)==reader['io_census']['total'] and len({v[0] for v in rows})==len(rows)
   assert all(len(v)==8 and all(x>=0 for x in v) and v[6] in (0,1) and v[7] in (0,1) for v in rows)
   byid={v[0]:v for v in rows};retained={q['id'] for q in reader['ios']}
   for q in reader['ios']:
    a=q['initial_admission'];b=q['completion_admission']
    assert [q['id'],q['callback_us']-q['submit_us'],a['dequeued_us']-q['submit_us'],a['group_run_us']-a['group_enter_us'],b['dequeued_us']-q['completion_submit_us'],b['group_run_us']-b['group_enter_us'],int(a['queued']),int(b['queued'])]==byid[q['id']]
    for p,st,en in ((a,q['submit_us'],q['worker_us']),(b,q['completion_submit_us'],q['callback_us'])):
     assert p['limit']==arm and p['pool'] and p['group'] and st<=p['dequeued_us']<=p['group_enter_us']<=p['group_gate_us']<=p['group_run_us']<=en
     assert p['queued']==(p['running']==p['limit'])
     for key in ('first_blocked','last_blocked','last_allowed'):
      v=p[key]
      if v is None:continue
      assert st<=v['at_us']<=p['dequeued_us'] and v['pool']==p['pool'] and v['queue']>0
      assert v['active']>=v['long']+v['waiting']
      assert (v['active']-v['long']-v['waiting']>v['concurrency'])==(key!='last_allowed')
   timers.extend(rows)
  prepare=[v/1000 for loader in r['loaders'] for v in loader['durations_us']['prepare']];assert len(prepare)==63
  assert on or not r['captures']
  global_ms=[v[i]/1000 for v in timers for i in (2,4)];group_ms=[v[i]/1000 for v in timers for i in (3,5)]
  fork=[v['end_ms']-v['start_ms'] for v in r['trace']['spans'] if v['kind']=='fork'];assert len(fork)==21
  phase_totals={phase:dist([sum(loader['durations_us'][phase])/1000 for loader in r['loaders']]) for phase in ('prepare','order_insert','item_insert','stock_update','commit')}
  runs.append(dict(phase_totals=phase_totals,name=r['name'],pool_mib=r['pool_mib'],variant=r['variant'],cap_phases={phase:sum(v['phase']==phase for v in events) for phase in ('load','recovery')},resolved_caps=sorted({v['resolved'] for v in events}),kind=r['kind'],pair=r['block'],read_threads=arm,observe=on,wall_ms=r['trace']['elapsed_ms'],cpu_ms=float(m['cpu_ms']),peak_rss_mib=int(m['maxrss_bytes_darwin'])/2**20,prepare=dist(prepare),fork=dist(fork),global_queue=dist(global_ms),group_queue=dist(group_ms),read_requests=len(timers) if on else None,requests_with_global_ge100ms=sum(max(v[2],v[4])>=100000 for v in timers) if on else None,profile_count=len(r['captures'])))
 groups=[];pairs=[]
 for on in (False,True):
  for variant in ('16','8'):
   selected=[r for r in runs if r['kind']=='natural' and r['observe']==on and r['variant']==variant];assert len(selected)==5
   groups.append(dict(observe=on,variant=variant,pool_mib=int(variant),read_threads=1,wall_min_ms=min(r['wall_ms'] for r in selected),wall_max_ms=max(r['wall_ms'] for r in selected),wall_mad_ms=round(statistics.median(abs(r['wall_ms']-statistics.median(v['wall_ms'] for v in selected)) for r in selected),3),wall_median_ms=round(statistics.median(r['wall_ms'] for r in selected),3),cpu_median_ms=round(statistics.median(r['cpu_ms'] for r in selected),3),fork_p50_median_ms=round(statistics.median(r['fork']['p50_ms'] for r in selected),3),fork_p95_median_ms=round(statistics.median(r['fork']['p95_ms'] for r in selected),3),peak_rss_median_mib=round(statistics.median(r['peak_rss_mib'] for r in selected),3),prepare_ge100ms=sum(r['prepare']['ge100ms'] for r in selected),runs_with_prepare_ge100ms=sum(r['prepare']['ge100ms']>0 for r in selected),read_requests=sum(r['read_requests'] for r in selected) if on else None,requests_with_global_ge100ms=sum(r['requests_with_global_ge100ms'] for r in selected) if on else None,global_stage_ge100ms=sum(r['global_queue']['ge100ms'] for r in selected) if on else None,group_stage_ge100ms=sum(r['group_queue']['ge100ms'] for r in selected) if on else None,global_p95_median_ms=round(statistics.median(r['global_queue']['p95_ms'] for r in selected),3) if on else None,global_p99_median_ms=round(statistics.median(r['global_queue']['p99_ms'] for r in selected),3) if on else None))
   groups[-1]['sample_phase_total_median_ms']={phase:round(statistics.median(r['phase_totals'][phase]['p50_ms'] for r in selected),3) for phase in selected[0]['phase_totals']}
  for pair in range(5):
   selected=[r for r in runs if r['kind']=='natural' and r['observe']==on and r['pair']==pair];assert len(selected)==2
   a=next(r for r in selected if r['variant']=='16');b=next(r for r in selected if r['variant']=='8')
   pairs.append(dict(observe=on,pair=pair,wall_delta_ms=round(b['wall_ms']-a['wall_ms'],3),wall_delta_pct=round((b['wall_ms']/a['wall_ms']-1)*100,2),cpu_delta_pct=round((b['cpu_ms']/a['cpu_ms']-1)*100,2),peak_rss_delta_mib=round(b['peak_rss_mib']-a['peak_rss_mib'],3)))
 profiles=[]
 for r in obs:
  for c in r['captures']:
   text=(HERE/c['retained_profile']).read_text();assert hashlib.sha256(text.encode()).hexdigest()==c['profile_sha256']
   assert c['call_enter_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=c['call_return_us'] and c['usable']
   for block in text.split('\n\n'):
    labels=next((json.loads(line[10:]) for line in block.splitlines() if line.startswith('# labels: ')),{})
    if labels.get('db_id')!=c['db_id'] or 'read_scope' not in labels or not re.search(r'\.Fn7142\b',block):continue
    reader=next(v for v in r['read_observers'] if v['db_id']==c['db_id']);scope=next(v for v in reader['scopes'] if v['id']==int(labels['read_scope']))
    assert scope['start_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=scope['end_us']
    before=next(v for v in c['read_before'] if v['scope_id']==scope['id']);after=next(v for v in c['read_after'] if v['scope_id']==scope['id'])
    for wait in scope['waits'] or []:
     if not wait['register_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=wait['return_us']:continue
     assert wait['id'] in before['active_wait_ids'] and wait['id'] in after['active_wait_ids'] and wait['io_id']==wait['notify_io_id']
     q=next(v for v in reader['ios'] if v['id']==wait['notify_io_id']);assert q['space']==scope['entry']['space'] and q['page']==scope['entry']['page'] and q['block']==scope['block']
     a=q['initial_admission'];b=q['completion_admission']
     profiles.append(dict(run=r['name'],variant=r['variant'],read_threads=r['read_threads'],db=c['db_id'],scope=scope['id'],io=q['id'],page=[q['space'],q['page']],prepare_ordinal=c['prepare_ordinal'],prepare_ms=(c['call_return_us']-c['call_enter_us'])/1000,initial_global_ms=(a['dequeued_us']-q['submit_us'])/1000,completion_global_ms=(b['dequeued_us']-q['completion_submit_us'])/1000,initial_group_ms=(a['group_run_us']-a['group_enter_us'])/1000,completion_group_ms=(b['group_run_us']-b['group_enter_us'])/1000,sync_io_ms=(q['sync_end_us']-q['worker_us'])/1000,initial_first_blocked=a['first_blocked'],completion_first_blocked=b['first_blocked']))
 return dict(profiles=profiles,cases=casecount,closed_observers=closed,runs=runs,groups=groups,pairs=pairs,percentile_method='nearest rank, median arithmetic; per-run stage counts include two stages/read; correlated request counts are not independent stalls')

if __name__=='__main__':
 obs=json.loads((HERE/'observations.json').read_text());result=analyze(obs);data=(json.dumps(result,indent=2)+'\n').encode()
 if '--check' in sys.argv:
  assert data==(HERE/'summary.json').read_bytes()
  for name,sha in json.loads((HERE/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
  for kind in ('setting','cleanup','queue','coverage','notify','cap','pool'):
   mutated=copy.deepcopy(obs)
   if kind=='setting':mutated[0]['trace']['meta']['innodb_read_io_threads']='99'
   elif kind=='cleanup':mutated[0]['trace']['meta']['active_mappings_after']='1'
   elif kind=='queue':next(r for r in mutated[0]['read_observers'] if r['timing_census'])['timing_census'][0][2]=-1
   elif kind=='coverage':mutated.pop()
   elif kind=='cap':mutated[0]['cap_events'][0]['resolved']=999999
   elif kind=='pool':mutated[0]['pool_mib']=999
   else:
    if not result['profiles']:continue # Explicitly report profile-binding mutation unavailable.
    target=result['profiles'][-1];r=next(v for v in mutated if v['name']==target['run']);reader=next(v for v in r['read_observers'] if v['db_id']==target['db']);scope=next(v for v in reader['scopes'] if v['id']==target['scope']);scope['waits'][0]['notify_io_id']=999999
   try:analyze(mutated)
   except (AssertionError,StopIteration):pass
   else:raise AssertionError('accepted '+kind)
  print('PASS readonly summary/checksums and settings/cleanup/queue/coverage/cap/pool mutations; notify mutation '+('PASS' if result['profiles'] else 'SKIP (no foreground read profile)'))
 else:(HERE/'summary.json').write_bytes(data);print(json.dumps({'groups':result['groups'],'pairs':result['pairs']},indent=2))
