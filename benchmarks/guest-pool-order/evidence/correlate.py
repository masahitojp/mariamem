from pathlib import Path
import json,gzip,collections,bisect
w=Path(__file__).resolve().parent.parent;e=w/'evidence';r=w/'worktree';names={int(l.split(':',1)[0]):l.split(':',1)[1]for l in gzip.decompress((r/'benchmarks/insert-wait-owner/evidence/function-map.txt.gz').read_bytes()).decode().splitlines()};report=[]
for i in range(8):
 xs=json.loads((e/f'events-{i}.json').read_text());by_pool=collections.defaultdict(list);queued=collections.defaultdict(collections.deque);pairs=[];executing={};accounted={};buf=[];holds=[]
 for x in xs:
  key=(x['instance'],x['pool']);by_pool[key].append(x);thread=(x['instance'],x['gid']);kind=x['event']
  if kind=='enqueue':queued[(key,x['task'])].append(x)
  elif kind=='dequeue'and queued[(key,x['task'])]:pairs.append((queued[(key,x['task'])].popleft(),x))
  elif kind=='execute_begin':executing[thread]=x
  elif kind=='execute_end':executing.pop(thread,None)
  elif kind=='wait_accounted':accounted[thread]=True
  elif kind=='wait_unaccounted':accounted[thread]=False
  elif kind=='futex_begin'and any('buf_load' in names.get(int(n),'') for n in x['frames']) and any('os_aio_wait_until_no_pending_reads' in names.get(int(n),'') for n in x['frames']):
   buf.append({'wait':x,'accounted':accounted.get(thread,False),'executing':executing.get(thread),'symbols':{n:names.get(int(n))for n in x['frames']}})
  elif kind=='hold_begin':holds.append(x)
 times={k:[x['ns']for x in v]for k,v in by_pool.items()};seen=0;examples=[]
 for a,b in pairs:
  key=(a['instance'],a['pool']);v=by_pool[key];ts=times[key];interval=v[bisect.bisect_left(ts,a['ns']):bisect.bisect_right(ts,b['ns'])]
  rejects=[x for x in interval if x['event']=='reject_pending']
  if rejects:
   seen+=1;examples.append({'ms':(b['ns']-a['ns'])/1e6,'enqueue':a,'dequeue':b,'reject_first':rejects[0],'clear':[x for x in interval if x['event']=='pending_clear'],'accounting':[x for x in interval if x['event']=='wait_accounted'],'hold_end':[x for x in interval if x['event']=='hold_end']})
 row={'run':i,'pending_exposed_tasks':seen,'longest_examples':sorted(examples,key=lambda x:x['ms'],reverse=True)[:3],'buf_load_futex':len(buf),'buf_load_accounted':sum(x['accounted']for x in buf),'buf_load_task_context':sum(x['executing']is not None for x in buf),'buf_load_examples':buf[:3],'hold_count':len(holds)};report.append(row);print(i,'pending-exposed',seen,'bufwait',len(buf),'accounted',row['buf_load_accounted'],'task',row['buf_load_task_context'],'holds',len(holds),flush=True)
(e/'correlation.json').write_text(json.dumps(report,indent=2))
