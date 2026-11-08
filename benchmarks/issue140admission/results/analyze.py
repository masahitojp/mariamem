"""Read-only replay of same-request global and group admission attribution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from dispatch_replay import analyze as dispatch
HERE=Path(__file__).resolve().parent

def timing(q):
 a=q['initial_admission'];b=q['completion_admission']
 return [q['id'],q['callback_us']-q['submit_us'],a['dequeued_us']-q['submit_us'],a['group_run_us']-a['group_enter_us'],b['dequeued_us']-q['completion_submit_us'],b['group_run_us']-b['group_enter_us'],int(a['queued']),int(b['queued'])]

def analyze(obs):
 result=dispatch(obs);result['admission_census']=[]
 for run in obs:
  metrics=[]
  for reader in run['read_observers']:
   rows=reader['timing_census'];assert len(rows)==reader['io_census']['total']
   assert len({v[0] for v in rows})==len(rows)
   by_id={v[0]:v for v in rows}
   for row in rows:assert len(row)==8 and all(v>=0 for v in row) and row[6] in (0,1) and row[7] in (0,1)
   retained={q['id'] for q in reader['ios'] or []}
   assert all(row[0] in retained for row in rows if row[1]>=50000)
   for q in reader['ios'] or []:
    assert timing(q)==by_id[q['id']]
    for name,start,end in [('initial_admission','submit_us','worker_us'),('completion_admission','completion_submit_us','callback_us')]:
     p=q[name];assert p['pool'] and p['group'] and p['limit']>=1
     assert q[start]<=p['dequeued_us']<=p['group_enter_us']<=p['group_gate_us']<=p['group_run_us']<=q[end]
     assert p['queued']==(p['running']==p['limit'])
     assert bool(p['blocked_count'])==bool(p['first_blocked'])==bool(p['last_blocked'])
     for state_name in ('first_blocked','last_blocked','last_allowed'):
      state=p[state_name]
      if state is None:continue
      assert state['pool']==p['pool'] and state['queue']>0 and state['active']>=state['long']+state['waiting']
      assert q[start]<=state['at_us']<=p['dequeued_us']
      blocked=state['active']-state['long']-state['waiting']>state['concurrency']
      assert blocked==(state_name!='last_allowed')
     if p['first_blocked']:assert p['first_blocked']['at_us']<=p['last_blocked']['at_us']
   metrics.extend(rows)
  long=[v for v in metrics if v[1]>=100000]
  result['admission_census'].append({'run':run['name'],'read_requests':len(metrics),'read_requests_ge100ms':len(long),'with_global_stage_ge100ms':sum(max(v[2],v[4])>=100000 for v in long),'with_group_stage_ge100ms':sum(max(v[3],v[5])>=100000 for v in long),'max_group_enter_to_run_ms':round(max((max(v[3],v[5]) for v in metrics),default=0)/1000,3),'group_queued_stages':sum(v[6]+v[7] for v in metrics)})
 for row in result['profile_bound_prepares']:
  run=next(v for v in obs if v['name']==row['run']);reader=next(v for v in run['read_observers'] if v['db_id']==row['db_id']);q=next(q for q in reader['ios'] if q['id']==row['io_id'])
  row.update(initial_global_queue_ms=round((q['initial_admission']['dequeued_us']-q['submit_us'])/1000,3),initial_group_ms=round((q['initial_admission']['group_run_us']-q['initial_admission']['group_enter_us'])/1000,3),completion_global_queue_ms=round((q['completion_admission']['dequeued_us']-q['completion_submit_us'])/1000,3),completion_group_ms=round((q['completion_admission']['group_run_us']-q['completion_admission']['group_enter_us'])/1000,3),initial_group_queued=q['initial_admission']['queued'],completion_group_queued=q['completion_admission']['queued'],completion_gate_first_blocked=q['completion_admission']['first_blocked'],completion_gate_last_blocked=q['completion_admission']['last_blocked'],completion_gate_last_allowed=q['completion_admission']['last_allowed'])
 return result

obs=json.loads((HERE/'observations.json').read_text());summary=analyze(obs);data=(json.dumps(summary,indent=2)+'\n').encode()
if '--check' in sys.argv:
 assert data==(HERE/'summary.json').read_bytes()
 for name,sha in json.loads((HERE/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
 target=summary['profile_bound_prepares'][0]
 for kind in ('counter','pool','dequeue','membership'):
  changed=copy.deepcopy(obs);run=next(v for v in changed if v['name']==target['run']);reader=next(v for v in run['read_observers'] if v['db_id']==target['db_id']);q=next(v for v in reader['ios'] if v['id']==target['io_id']);p=q['completion_admission']
  if kind=='counter':p['first_blocked']['active']=0
  elif kind=='pool':p['first_blocked']['pool']+=4
  elif kind=='dequeue':p['dequeued_us']=q['callback_us']+1
  else:next(s for s in reader['scopes'] if s['id']==target['scope_id'])['waits'][0]['notify_io_id']=999999
  try:analyze(changed)
  except (AssertionError,StopIteration,KeyError):pass
  else:raise AssertionError('accepted wrong '+kind)
 print('PASS: request/page/notify binding, admission chronology, locked gate formula, all-request timing census, four mutations and checksums (read-only)')
else:(HERE/'summary.json').write_bytes(data)
