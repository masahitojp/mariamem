"""Queue-distribution acceptance for the bounded read1 accounting prototype."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def enc(x):return (json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def distribution(xs):
 xs=sorted(xs);assert xs
 return dict(n=len(xs),p50=statistics.median(xs),p95=xs[int(.95*(len(xs)-1))],p99=xs[int(.99*(len(xs)-1))],max=max(xs),over_ms={str(k):sum(v>k for v in xs) for k in [1,10,50,100,250,500]})
def reduce_trace(path,report,variant):
 t=json.loads(path.read_text());assert t['dropped']==0 and not t['stacks'];assert not t['routine_stack_capture'] and not t['atomic_wait_notify_hooks']
 es=sorted(t['events'],key=lambda e:e['ns']);sp=collections.defaultdict(list);bindings={};pool_policy={}
 for e in es:
  sp[e['span']].append(e)
  if e['kind']=='instance_child':bindings[e['instance']]=e['a']
 assert len(bindings)==49 and set(bindings.values())=={-1,*range(48)}
 pairs=[]
 for xs in sp.values():
  a,b=xs[0],xs[-1]
  if a['kind'].endswith('_begin'):
   assert b['kind']==a['kind'][:-6]+'_end',(a,b);pairs.append((a,b))
  if a['kind']=='pool_policy':
   assert [e['kind'] for e in xs]==['pool_policy','pool_counts','pool_waiting']
   pool_policy[a['span']]=dict(instance=a['instance'],thread=a['thread'],ns=a['ns'],waiting=xs[2]['b'])
 pending=collections.defaultdict(collections.deque);bychild=collections.defaultdict(list);root=[]
 for e in es:
  key=e['instance'],e['b']
  if e['kind']=='submit_begin':pending[key].append(e)
  elif e['kind']=='task_start':
   assert pending[key];u=pending[key].popleft();ms=(e['ns']-u['ns'])/1e6;assert ms>=0
   child=bindings[e['instance']]
   (root if child==-1 else bychild[child]).append(ms)
 assert set(bychild)==set(range(48))
 canceled=sum(len(xs) for (ii,task),xs in pending.items() if bindings[ii]>=0)
 read_scopes=[(a,b) for a,b in pairs if a['kind']=='read_wait_begin'];accounts=[(a,b) for a,b in pairs if a['kind']=='account_null_begin']
 null=[(a,b) for a,b in read_scopes if a['b']==0];nonnull=[(a,b) for a,b in read_scopes if a['b']!=0]
 for a,b in accounts:
  assert a['c']&4==0,'already-WAITING entry would risk nested accounting'
  owners=[(u,v) for u,v in null if u['instance']==a['instance'] and u['thread']==a['thread'] and u['ns']<=a['ns']<=b['ns']<=v['ns']]
  assert len(owners)==1
 for a,b in null:
  n=sum(u['instance']==a['instance'] and u['thread']==a['thread'] and a['ns']<=u['ns']<=v['ns']<=b['ns'] for u,v in accounts)
  assert n==(1 if variant=='fixed' else 0),(variant,n)
 for a,b in nonnull:assert not any(u['instance']==a['instance'] and u['thread']==a['thread'] and a['ns']<=u['ns']<=b['ns'] for u,v in accounts)
 real_pool_accounts=0
 for a,b in accounts:
  if a['b'] and any(p['instance']==a['instance'] and p['thread']==a['thread'] and a['ns']<=p['ns']<=b['ns'] and p['waiting']>0 for p in pool_policy.values()):real_pool_accounts+=1
 allq=sorted(v for xs in bychild.values() for v in xs)
 childmax=[max(bychild[k]) for k in range(48)]
 return dict(event_count=len(es),dropped=0,queue_ms_sorted=allq,child_max_queue_ms=childmax,per_child_task_counts=[len(bychild[k]) for k in range(48)],censored_child_submits=canceled,root_queue=distribution(root),null_read_scopes=len(null),nonnull_read_scopes=len(nonnull),account_null_pairs=len(accounts),real_pool_account_scopes=real_pool_accounts,trace_sha256=sha(path),already_waiting_entries=0)

def summarize(d):
 groups=collections.defaultdict(list);pairs=collections.defaultdict(dict)
 for name,r in sorted(d['runs'].items()):groups[r['variant']].append(r);pairs[r['repetition']][r['variant']]=r
 assert set(groups)=={'baseline','fixed'} and all(len(v)==3 for v in groups.values()) and len(pairs)==3
 out={'variants':{},'pairs':[]}
 for variant,rs in groups.items():
  out['variants'][variant]=dict(child_max_queue_ms=distribution([x for r in rs for x in r['child_max_queue_ms']]),per_task_queue_ms=d['pooled_task_queue_distributions'][variant],censored_child_submits=sum(r['censored_child_submits'] for r in rs),account_null_pairs=sum(r['account_null_pairs'] for r in rs),real_pool_account_scopes=sum(r['real_pool_account_scopes'] for r in rs),count_ms=distribution([s['count_ms'] for r in rs for s in r['samples']]),batch_ms=[r['batch_ms'] for r in rs])
 support=0
 for rep,p in sorted(pairs.items()):
  b=distribution(p['baseline']['child_max_queue_ms']);f=distribution(p['fixed']['child_max_queue_ms'])
  yes=f['p95']<=b['p95'] and f['p99']<=b['p99'] and (f['p95']<b['p95'] or f['p99']<b['p99']);support+=yes
  out['pairs'].append(dict(repetition=rep,baseline=b,fixed=f,tail_support=bool(yes)))
 b=out['variants']['baseline']['child_max_queue_ms'];f=out['variants']['fixed']['child_max_queue_ms']
 controls=all(v['result']=='PASS' and v['no_pool_guard'] and v['long_task_guard'] and v['fixed']==(mode=='fixed') and v['nonnull_true']==dict(begin=1,end=1) and v['nonnull_false']==dict(begin=int(mode=='fixed'),end=int(mode=='fixed')) for mode,v in d['controls'].items())
 mechanical=controls and out['variants']['fixed']['real_pool_account_scopes']>0 and all(r['censored_child_submits']==0 and r['already_waiting_entries']==0 for r in d['runs'].values())
 nonworse=all(f[k]<=b[k] for k in ['p50','p95','p99']);strict=f['p95']<b['p95'] or f['p99']<b['p99']
 out['assessment']=dict(result='SUPPORTS_GUEST_CANDIDATE' if mechanical and nonworse and strict and support>=2 else 'INCONCLUSIVE_OR_REGRESSION',mechanical_and_censor_gate=mechanical,pooled_child_distribution_nonworse=nonworse,pooled_tail_improves=strict,supporting_pairs=support,required_pairs=2,criterion='Queue-delay distributions; no 400ms disappearance gate',scope='Normal-path generated prototype; not canonical guest/WASM qualification')
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  E=a.evidence;d=dict(inputs=json.loads((E/'inputs.json').read_text()),controls={},runs={});all_task_queues=collections.defaultdict(list);records=json.loads((E/'measure-records.json').read_text());assert len(records)==6
  for mode in ['baseline','fixed']:
   c=json.loads((E/('controls-'+mode+'.json')).read_text());assert c['fixed']==(mode=='fixed') and c['result']=='PASS'
   assert c['nonnull_true']==dict(begin=1,end=1) and c['nonnull_false']==dict(begin=int(mode=='fixed'),end=int(mode=='fixed'));d['controls'][mode]=c
  for rec in records:
   path=E/rec['report'];r=json.loads(path.read_text());variant=rec['variant'];assert r['wait_accounting_enabled']==(variant=='fixed') and r['success'] and r['cleanup_complete'] and r['root_closed_before_forks']
   expected=dict(read=1,write=2,purge=1,native_aio=0);assert r['io_profile']==expected and len(r['samples'])==48 and {s['index'] for s in r['samples']}==set(range(48))
   assert all(s['oracle'] and s['cleanup_complete'] and s['io_profile']==expected for s in r['samples'])
   assert not (E/rec['report'].replace('.json','.stderr.txt')).read_bytes()
   trace=reduce_trace(Path(str(path)+'.trace.json'),r,variant);task_queues=trace.pop('queue_ms_sorted');all_task_queues[variant].extend(task_queues);trace['per_task_queue_distribution']=distribution(task_queues);trace.update(variant=variant,repetition=rec['repetition'],batch_ms=r['batch_ms'],cpu_ms=r['cpu_user_ms']+r['cpu_system_ms'],lifetime_max_rss_bytes=r['lifetime_max_rss_bytes'],samples=[{k:s[k] for k in ['index','count_ms','query_ms','fork_ms','oracle','cleanup_complete']} for s in sorted(r['samples'],key=lambda x:x['index'])],report_sha256=sha(path));d['runs'][rec['report']]=trace
  d['pooled_task_queue_distributions']={mode:distribution(xs) for mode,xs in sorted(all_task_queues.items())}
  data=(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n').encode()
  if a.check:assert (R/'compact.json').read_bytes()==data
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(data)
 else:d=json.loads((R/'compact.json').read_text())
 data=enc(summarize(d))
 if a.check:
  assert (R/'summary.json').read_bytes()==data
  for n,h in json.loads((R/'SHA256SUMS.json').read_text()).items():assert sha(R/n)==h,n
  print('CHECK PASS: functional/accounting/distribution gate and hashes'+('; raw reduction' if a.evidence else ''))
 else:(R/'summary.json').write_bytes(data)
if __name__=='__main__':main()
