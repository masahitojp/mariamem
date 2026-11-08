"""Preserve compact all-request timing census; reduce short request metadata."""
from pathlib import Path
import json,hashlib,shutil,sys
w=Path(sys.argv[1]).resolve();e=w/'evidence';out=e/'report';out.mkdir(exist_ok=True)
obs=json.loads((e/'observations.json').read_text())
for run in obs:
 readers=json.loads((e/run.pop('read_file')).read_text()) or []
 for r in readers:
  ios=r['ios'] or [];r['timing_census']=[]
  for q in ios:
   a=q['initial_admission'];b=q['completion_admission']
   # Include both measured intervals and capture offsets for all requests.
   row=[q['id'],q['callback_us']-q['submit_us'],a['dequeued_us']-q['submit_us'],a['group_run_us']-a['group_enter_us'],b['dequeued_us']-q['completion_submit_us'],b['group_run_us']-b['group_enter_us'],int(a['queued']),int(b['queued'])]
   assert q['submit_us']<=a['dequeued_us']<=a['group_enter_us']<=a['group_gate_us']<=a['group_run_us']<=q['worker_us']<=q['sync_end_us']<=q['completion_submit_us']<=b['dequeued_us']<=b['group_enter_us']<=b['group_gate_us']<=b['group_run_us']<=q['callback_us']<=q['callback_return_us']
   assert a['limit']==b['limit']==run['read_threads']
   r['timing_census'].append(row)
  referenced={v.get(k) for sc in r['scopes'] or [] for v in sc['waits'] or [] for k in ('io_id','notify_io_id')}
  retained=[q for q in ios if q['id'] in referenced]
  omitted=[q for q in ios if q not in retained]
  r['io_census']={'total':len(ios),'retained':len(retained),'omitted_unreferenced_metadata':len(omitted),'omitted_sha256':hashlib.sha256(json.dumps(omitted,sort_keys=True,separators=(',',':')).encode()).hexdigest()};r['ios']=retained
 run['read_observers']=readers
 for c in run['captures']:
  name=run['name']+'-'+c['profile_file'];src=e/run['name']/c['profile_file'];assert hashlib.sha256(src.read_bytes()).hexdigest()==c['profile_sha256'];shutil.copyfile(src,out/name);c['retained_profile']=name
(out/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n')
for name in ('inputs.json','unit.txt'):shutil.copyfile(e/name,out/name)
print('reduced',len(obs),'processes;',sum(p.stat().st_size for p in out.iterdir()),'bytes')
