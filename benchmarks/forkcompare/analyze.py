"""Recompute compact diagnostic evidence. --check never changes stored evidence."""
import argparse, collections, hashlib, json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(x):return (json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def reduce_trace(path):
 d=json.loads(path.read_text());assert d['dropped']==0
 es=sorted(d['events'],key=lambda e:e['ns']);st=d['stacks'];spans=collections.defaultdict(list);inst=collections.defaultdict(list)
 for e in es:spans[e['span']].append(e);inst[e['instance']].append(e)
 def stack(e):return st[e['stack']-1] if e['stack'] else []
 pairs=[]
 for ee in spans.values():
  a,b=ee[0],ee[-1]
  if a['kind'].endswith('_begin'):
   assert b['kind']==a['kind'][:-6]+'_end',(a,b)
   pairs.append((a,b,(b['ns']-a['ns'])/1e6))
 # Every entered atomic wait returned, including non-equal and timeouts.
 waits=[]
 for ee in spans.values():
  if ee[0]['kind']=='wait_enter':
   assert ee[-1]['kind']=='wait_return'
   waits.append((ee[0],ee[-1]))
 queue=collections.defaultdict(collections.deque);tasks=[]
 for e in es:
  key=(e['instance'],e['b'])
  if e['kind']=='submit_begin':queue[key].append(e)
  elif e['kind']=='task_start':
   assert queue[key],('task without submit',e)
   a=queue[key].popleft();tasks.append((a,e,(e['ns']-a['ns'])/1e6))
 # Submits may be canceled at shutdown; never invent an execution for them.
 client=[dict(child=a['a'],begin_ms=a['ns']/1e6,end_ms=b['ns']/1e6,duration_ms=ms) for a,b,ms in pairs if a['kind']=='client_count_begin']
 reads=[(a,b,ms) for a,b,ms in pairs if a['kind']=='read_wait_begin' and ms>100]
 cases=[]
 for a,b,ms in reads:
  ii=a['instance'];ie=inst[ii];window=[x for x in ie if a['ns']<=x['ns']<=b['ns']]
  maint=[]
  for m in window:
   if m['kind']!='maintenance_begin':continue
   end=spans[m['span']][-1]
   policies=[x for x in window if x['kind']=='pool_policy' and x['thread']==m['thread'] and m['ns']<=x['ns']<=end['ns']]
   policy=[]
   for x in policies:
    ee=spans[x['span']];assert [v['kind'] for v in ee]==['pool_policy','pool_counts','pool_waiting']
    policy.append(dict(queue_tail=x['b'],queue_head=x['c'],active=ee[1]['a'],standby=ee[1]['b'],concurrency=ee[1]['c'],long_tasks=ee[2]['a'],accounted_waiting=ee[2]['b']))
   maint.append(dict(offset_ms=(m['ns']-a['ns'])/1e6,policies=policy,thread=m['thread'],span=m['span']))
  ww=[]
  for w,r in waits:
   if w['instance']!=ii or w['thread']!=a['thread'] or not(a['ns']<=w['ns']<=r['ns']<=b['ns']):continue
   if (r['ns']-w['ns'])<100e6:continue
   notifies=[x for x in ie if x['kind']=='notify_enter' and x['a']==w['a'] and w['ns']<=x['ns']<=r['ns']]
   ns=[]
   for n in notifies:
    ne=spans[n['span']][-1];assert ne['kind']=='notify_return'
    ns.append(dict(enter_ms=n['ns']/1e6,return_ms=ne['ns']/1e6,woken=ne['c'],thread=n['thread'],stack=stack(n),wait_return_minus_notify_enter_ms=(r['ns']-n['ns'])/1e6))
   ww.append(dict(begin_ms=w['ns']/1e6,end_ms=r['ns']/1e6,address=w['a'],timeout_ns=w['b'],result=r['c'],stack=stack(w),notifications=ns))
  queued=[(u,v,t) for u,v,t in tasks if u['instance']==ii and u['ns']<b['ns'] and v['ns']>a['ns']]
  worst=max(queued,key=lambda x:x[2],default=None)
  pread=[t for u,v,t in pairs if u['kind']=='pread_begin' and u['instance']==ii and a['ns']<=u['ns']<=b['ns']]
  starts=[dict(offset_ms=(x['ns']-a['ns'])/1e6,thread=x['thread'],tid=x['a']) for x in window if x['kind']=='thread_start']
  case=dict(instance=ii,thread=a['thread'],read_wait_begin_ms=a['ns']/1e6,read_wait_end_ms=b['ns']/1e6,read_wait_ms=ms,trx_is_null=a['b']==0,query_dispatch_in_stack=any('Fn14580' in f for f in stack(a)),read_stack=stack(a),maintenance=maint,atomic_waits=ww,new_threads=starts,read_calls_in_span=len(pread),max_pread_ms=max(pread,default=None))
  if worst:
   u,v,t=worst;case['longest_task_submit_to_start']=dict(task=u['b'],submit_begin_ms=u['ns']/1e6,submit_end_ms=spans[u['span']][-1]['ns']/1e6,start_ms=v['ns']/1e6,delay_ms=t,worker_thread=v['thread'],submit_stack=stack(u))
  cases.append(case)
 return dict(trace_sha256=sha(path),event_count=len(es),dropped=d['dropped'],client_counts=client,long_read_waits=cases,max_pread_ms=max(t for a,b,t in pairs if a['kind']=='pread_begin'),max_submit_to_start_ms=max(t for a,b,t in tasks),unexecuted_submits=sum(map(len,queue.values())))

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  E=a.evidence;out={'inputs':json.loads((E/'inputs.json').read_text()),'runs':{}}
  records=json.loads((E/'measure-records.json').read_text());assert len(records)==8
  for rec in records:
   f=E/rec['report'];r=json.loads(f.read_text());assert r['success'] and r['cleanup_complete'] and all(x['oracle'] and x['cleanup_complete'] for x in r['samples'])
   assert len(r['samples'])==48
   trace=reduce_trace(Path(str(f)+'.trace.json'));trace['report_sha256']=sha(f);trace['sample_count']=len(r['samples']);trace['successful_oracles']=sum(x['oracle'] and x['cleanup_complete'] for x in r['samples']);trace['warmup']=rec['warmup'];out['runs'][rec['report']]=trace
  # Pilot failures retain their failed outcome; validate separately from normal runs.
  for rec in json.loads((E/'pilot-records.json').read_text()):
   r=json.loads((E/rec['report']).read_text());assert r['cleanup_complete']
   assert r['success'] is (not rec['negative'])
  blob=encoded(out)
  if a.check:assert (R/'compact.json').read_bytes()==blob
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(blob)
 else:
  out=json.loads((R/'compact.json').read_text())
 summary=[]
 for name,r in out['runs'].items():
  if r['warmup']:continue
  assert r['dropped']==0
  summary.append(dict(run=name,slow_counts=[c for c in r['client_counts'] if c['duration_ms']>100],long_read_waits=[dict(instance=c['instance'],ms=c['read_wait_ms'],query=c['query_dispatch_in_stack'],maintenance_ticks=len(c['maintenance'])) for c in r['long_read_waits']],max_pread_ms=r['max_pread_ms'],max_submit_to_start_ms=r['max_submit_to_start_ms'],event_count=r['event_count']))
 blob=encoded(summary)
 if a.check:
  assert (R/'summary.json').read_bytes()==blob
  hashes=json.loads((R/'SHA256SUMS.json').read_text())
  for name,digest in hashes.items():assert sha(R/name)==digest,name
  print('CHECK PASS: read-only summary recomputation and checksums'+('; full raw trace reduction' if a.evidence else ''))
 else:(R/'summary.json').write_bytes(blob)
if __name__=='__main__':main()
