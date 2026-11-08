"""Recompute same-request dispatch attribution from compact retained observations."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from read_replay import summarize
HERE=Path(__file__).resolve().parent

def analyze(obs):
 result=summarize(obs)
 result['io_census']=[]
 for run in obs:
  total=kept=0
  for reader in run['read_observers']:
   census=reader['io_census'];qs=reader['ios'] or []
   assert census['total']==census['retained']+census['omitted_short_unreferenced'] and census['retained']==len(qs) and census['incomplete']==0
   assert len({q['id'] for q in qs})==len(qs)
   total+=census['total'];kept+=len(qs)
   for q in qs:
    assert q['submit_us']<=q['worker_us']<=q['sync_end_us']<=q['completion_submit_us']<=q['callback_us']<=q['callback_return_us']
    assert q['submit_us']<=q['submit_return_us'] and q['completion_submit_us']<=q['completion_submit_return_us']
   for scope in reader['scopes'] or []:
    for wait in scope['waits'] or []:
     if not wait['notify_io_id']:continue
     assert wait['io_id']==wait['notify_io_id']
     q=next(q for q in qs if q['id']==wait['notify_io_id'])
     assert q['block']==scope['block'] and q['space']==scope['entry']['space'] and q['page']==scope['entry']['page']
     assert q['callback_us']<=wait['signal_before_us']<=q['callback_return_us']
  result['io_census'].append({'run':run['name'],'total':total,'retained':kept,'omitted_short_unreferenced':total-kept})
 for row in result['profile_bound_prepares']:
  run=next(r for r in obs if r['name']==row['run']);capture=run['captures'][0];reader=next(r for r in run['read_observers'] if r['db_id']==row['db_id']);scope=next(s for s in reader['scopes'] if s['id']==row['scope_id']);assert len(scope['waits'])==1;wait=scope['waits'][0];assert wait['io_id']==wait['notify_io_id']!=0
  q=next(q for q in reader['ios'] if q['id']==wait['notify_io_id']);row.update(prepare_ordinal=capture['prepare_ordinal'],lane=capture['lane'],io_id=q['id'],cb=q['cb'],initial_dispatch_ms=round((q['worker_us']-q['submit_us'])/1000,3),initial_dispatch_after_submit_return_ms=round((q['worker_us']-q['submit_return_us'])/1000,3),synchronous_io_ms=round((q['sync_end_us']-q['worker_us'])/1000,3),completion_dispatch_ms=round((q['callback_us']-q['completion_submit_us'])/1000,3),completion_dispatch_after_submit_return_ms=round((q['callback_us']-q['completion_submit_return_us'])/1000,3),callback_to_notify_ms=round((wait['signal_before_us']-q['callback_us'])/1000,3))
 return result

obs=json.loads((HERE/'observations.json').read_text());summary=analyze(obs);data=(json.dumps(summary,indent=2)+'\n').encode()
if '--check' in sys.argv:
 assert data==(HERE/'summary.json').read_bytes()
 for name,sha in json.loads((HERE/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
 target=next(i for i,r in enumerate(obs) if not r['control'] and r['captures'])
 bound=summary['profile_bound_prepares'][0]
 for kind in ('notify_id','block','page','phase_time'):
  changed=copy.deepcopy(obs);run=changed[target];reader=next(r for r in run['read_observers'] if r['db_id']==bound['db_id']);scope=next(s for s in reader['scopes'] if s['id']==bound['scope_id']);wait=scope['waits'][0];q=next(q for q in reader['ios'] if q['id']==wait['notify_io_id'])
  if kind=='notify_id':wait['notify_io_id']=999999
  elif kind=='block':q['block']=0
  elif kind=='page':q['page']+=1
  else:q['worker_us']=q['callback_us']+1
  try:analyze(changed)
  except (AssertionError,StopIteration,KeyError):pass
  else:raise AssertionError('accepted wrong '+kind)
 print('PASS: page/profile/request-generation/notification binding, four mutations, phase order, census and checksums (read-only)')
else:(HERE/'summary.json').write_bytes(data)
