"""Bind slow read4 COUNT to its own guest pool; never infer child from timing alone."""
import argparse,collections,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def reduce_trace(path,report):
 t=json.loads(path.read_text());assert t['dropped']==0 and not t['routine_stack_capture'] and not t['atomic_wait_notify_hooks']
 assert not t['stacks'] and all(e['stack']==0 for e in t['events'])
 es=sorted(t['events'],key=lambda e:e['ns']);frames=t['stacks'];spans=collections.defaultdict(list);inst=collections.defaultdict(list)
 for e in es:spans[e['span']].append(e);inst[e['instance']].append(e)
 def stack(e):return frames[e['stack']-1] if e['stack'] else []
 bindings={e['a']:e['instance'] for e in es if e['kind']=='instance_child'}
 assert set(bindings)=={-1,*range(48)} and len(set(bindings.values()))==49
 pairs=[];waits=[]
 for xs in spans.values():
  a,b=xs[0],xs[-1]
  if a['kind'].endswith('_begin'):
   assert b['kind']==a['kind'][:-6]+'_end',(a,b);pairs.append((a,b,(b['ns']-a['ns'])/1e6))
  if a['kind']=='wait_enter':assert b['kind']=='wait_return';waits.append((a,b))
 policies={}
 for e in es:
  if e['kind']=='pool_policy':
   xs=spans[e['span']];assert [x['kind'] for x in xs]==['pool_policy','pool_counts','pool_waiting']
   active,standby,concurrency=xs[1]['a'],xs[1]['b'],xs[1]['c'];long,waiting=xs[2]['a'],xs[2]['b']
   policies[e['span']]=dict(ns=e['ns'],thread=e['thread'],queued=e['b']!=e['c'],queue_tail=e['b'],queue_head=e['c'],active=active,standby=standby,concurrency=concurrency,long_tasks=long,accounted_waiting=waiting,compensated_active=active-long-waiting,concurrency_gate_allows=active-long-waiting<=concurrency,stack=stack(e))
 queue=collections.defaultdict(collections.deque);tasks=[];running={}
 for e in es:
  key=(e['instance'],e['b'])
  if e['kind']=='submit_begin':queue[key].append(e)
  elif e['kind']=='task_start':
   assert queue[key],('unmatched task',e);u=queue[key].popleft();task=dict(instance=e['instance'],task=e['b'],callback=e['c'],submit_ns=u['ns'],start_ns=e['ns'],end_ns=None,worker_thread=e['thread'],queue_ms=(e['ns']-u['ns'])/1e6,submit_stack=stack(u));tasks.append(task);running[(e['instance'],e['thread'])]=task
  elif e['kind']=='task_end':
   task=running.pop((e['instance'],e['thread']));assert task['task']==e['b'] and task['callback']==e['c'];task['end_ns']=e['ns']
 assert not running
 clients=[(a,b,ms) for a,b,ms in pairs if a['kind']=='client_count_begin'];assert len(clients)==48 and {a['a'] for a,b,ms in clients}==set(range(48))
 sample={s['index']:s for s in report['samples']};cases=[]
 for a,b,ms in clients:
  if sample[a['a']]['count_ms']<=100:continue
  child=a['a'];ii=bindings[child];ie=inst[ii];start,end=a['ns'],b['ns'];window=[e for e in ie if start<=e['ns']<=end]
  window_spans={e['span'] for e in window};instance_spans={e['span'] for e in ie}
  ps=[v for k,v in policies.items() if k in window_spans]
  previous=[v for k,v in policies.items() if v['ns']<start and k in instance_spans]
  changes=[dict(ns=e['ns'],argument=e['a'],effective=e['b'],stack=stack(e)) for e in ie if e['kind']=='concurrency_store']
  ticks=[]
  for u,v,duration in pairs:
   if u['instance']==ii and u['kind']=='maintenance_begin' and start<=u['ns']<=end:
    ticks.append(dict(begin_ns=u['ns'],end_ns=v['ns'],duration_ms=duration,policies=[p for p in ps if p['thread']==u['thread'] and u['ns']<=p['ns']<=v['ns']]))
  reads=[dict(begin_ns=u['ns'],end_ns=v['ns'],duration_ms=duration,thread=u['thread'],trx_is_null=u['b']==0,query_scope_overlap=any(q['thread']==u['thread'] and q['ns']<=u['ns']<z['ns'] for q,z,_ in pairs if q['kind']=='query_scope_begin' and q['instance']==ii),background_load_scope_overlap=any(q['thread']==u['thread'] and q['ns']<=u['ns']<z['ns'] for q,z,_ in pairs if q['kind']=='background_load_scope_begin' and q['instance']==ii),stack=stack(u)) for u,v,duration in pairs if u['kind']=='read_wait_begin' and u['instance']==ii and duration>100 and u['ns']<end and v['ns']>start]
  ww=[]
  for u,v in waits:
   if u['instance']!=ii or (v['ns']-u['ns'])<=100e6 or u['ns']>=end or v['ns']<=start:continue
   notifications=[]
   for n in ie:
    if n['kind']=='notify_enter' and n['a']==u['a'] and u['ns']<=n['ns']<=v['ns']:
     nr=spans[n['span']][-1];assert nr['kind']=='notify_return'
     notifications.append(dict(enter_ns=n['ns'],return_ns=nr['ns'],woken=nr['c'],thread=n['thread'],wait_return_minus_notify_enter_ms=(v['ns']-n['ns'])/1e6,stack=stack(n)))
   ww.append(dict(begin_ns=u['ns'],end_ns=v['ns'],duration_ms=(v['ns']-u['ns'])/1e6,address=u['a'],thread=u['thread'],timeout_ns=u['b'],result=v['c'],stack=stack(u),notifications=notifications))
  ts=[x for x in tasks if x['instance']==ii and x['submit_ns']<end and x['start_ns']>start];ts=sorted(ts,key=lambda x:x['queue_ms'],reverse=True)
  adds=[]
  for u,v,duration in pairs:
   if u['instance']==ii and u['kind']=='add_thread_begin' and start<=u['ns']<=end:
    markers=[e for e in ie if e['thread']==u['thread'] and e['ns']<=u['ns'] and e['kind'] in ['policy_add_request','maintenance_stall_add_request']]
    marker=markers[-1] if markers else None
    adds.append(dict(begin_ns=u['ns'],end_ns=v['ns'],duration_ms=duration,thread=u['thread'],route=marker['kind'] if marker else 'unclassified',marker_ns=marker['ns'] if marker else None))
  cases.append(dict(child=child,instance=ii,count_begin_ns=start,count_end_ns=end,count_ms=sample[child]['count_ms'],recorded_client_ms=ms,guest_startup=sample[child]['startup_trace']['guest'],previous_policy=previous[-1] if previous else None,policies_during_count=ps,concurrency_changes=changes,maintenance=ticks,read_waits=reads,atomic_waits=ww,queued_tasks=ts[:8],add_thread_requests=adds,thread_starts=[e for e in window if e['kind']=='thread_start'],max_pread_ms=max((duration for u,v,duration in pairs if u['instance']==ii and u['kind']=='pread_begin' and u['ns']<end and v['ns']>start),default=None)))
 client_records=[]
 for a,b,ms in clients:
  changes=[e for e in inst[bindings[a['a']]] if e['kind']=='concurrency_store'];assert [[e['a'],e['b']] for e in changes]==[[0,16],[4,4],[0,16],[4,4],[0,16]]
  assert all(any(q['instance']==bindings[a['a']] and q['kind']=='background_load_scope_begin' and q['thread']==e['thread'] and q['ns']<=e['ns']<=z['ns'] for q,z,_ in pairs) for e in changes[3:])
  before=[e for e in changes if e['ns']<=a['ns']];assert before
  overlap=changes[3]['ns']<b['ns'] and changes[4]['ns']>a['ns']
  client_records.append(dict(child=a['a'],instance=bindings[a['a']],count_ms=sample[a['a']]['count_ms'],recorded_client_ms=ms,begin_ns=a['ns'],end_ns=b['ns'],concurrency_at_begin=before[-1]['b'],background_load_overlap=overlap,count_begin_minus_background_restore_ms=(a['ns']-changes[4]['ns'])/1e6))
 reads=[ms for a,b,ms in pairs if a['kind']=='read_wait_begin']
 return dict(trace_sha256=sha(path),event_count=len(es),dropped=t['dropped'],bindings={str(k):v for k,v in bindings.items()},clients=client_records,cases=cases,max_submit_to_start_ms=max(x['queue_ms'] for x in tasks),max_read_wait_ms=max(reads),long_read_waits_over_100ms=sum(v>100 for v in reads),unexecuted_submits=sum(map(len,queue.values())))

def summarize(d):
 out=[]
 for name,r in sorted(d['runs'].items()):
  assert r['dropped']==0 and len(r['clients'])==48
  out.append(dict(run=name,event_count=r['event_count'],triggered_stacks=r['triggered_stacks'],max_count_ms=max(c['count_ms'] for c in r['clients']),count_begin_concurrency4=sum(c['concurrency_at_begin']==4 for c in r['clients']),background_load_overlap_count=sum(c['background_load_overlap'] for c in r['clients']),max_read_wait_ms=r['max_read_wait_ms'],long_read_waits_over_100ms=r['long_read_waits_over_100ms'],slow_counts=[dict(child=c['child'],instance=c['instance'],count_ms=c['count_ms'],read_waits=[x['duration_ms'] for x in c['read_waits']],max_queue_ms=max((x['queue_ms'] for x in c['queued_tasks']),default=None),maintenance_ticks=len(c['maintenance']),policies=[dict(concurrency=p['concurrency'],active=p['active'],standby=p['standby'],waiting=p['accounted_waiting'],long_tasks=p['long_tasks'],gate_allows=p['concurrency_gate_allows']) for p in c['policies_during_count']],add_routes=[x['route'] for x in c['add_thread_requests']]) for c in r['cases']],max_submit_to_start_ms=r['max_submit_to_start_ms']))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  E=a.evidence;d=dict(inputs=json.loads((E/'inputs.json').read_text()),runs={});records=json.loads((E/'measure-records.json').read_text());assert len(records)==3
  for rec in records:
   path=E/rec['report'];r=json.loads(path.read_text());assert r['success'] and r['cleanup_complete'] and len(r['samples'])==48
   expected=dict(read=4,write=2,purge=1,native_aio=0);assert r['io_profile']==expected and all(s['oracle'] and s['cleanup_complete'] and s['io_profile']==expected for s in r['samples'])
   trace=reduce_trace(Path(str(path)+'.trace.json'),r);trace['report_sha256']=sha(path)
   captures=[]
   for meta in sorted(Path(str(path)[:-5]+'-stacks').glob('*.json')):
    info=json.loads(meta.read_text());assert 0<=info['child']<48;info['metadata_sha256']=sha(meta);info['text_sha256']=sha(meta.with_suffix('.txt'));info['path']=str(meta.relative_to(E));captures.append(info)
   assert len(captures)<=1
   trace['triggered_stacks']=captures;d['runs'][rec['report']]=trace
  blob=enc(d)
  if a.check:assert (R/'compact.json').read_bytes()==blob
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(blob)
 else:d=json.loads((R/'compact.json').read_text())
 blob=enc(summarize(d))
 if a.check:
  assert (R/'summary.json').read_bytes()==blob
  for n,h in json.loads((R/'SHA256SUMS.json').read_text()).items():assert sha(R/n)==h,n
  print('CHECK PASS: child-instance binding, traces, summary and hashes'+('; full raw reduction' if a.evidence else ''))
 else:(R/'summary.json').write_bytes(blob)
if __name__=='__main__':main()
