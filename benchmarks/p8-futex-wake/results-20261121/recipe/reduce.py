"""Resolve stacks with the audited name map and join slow foreground waits to samples."""
import csv,gzip,hashlib,json,re,statistics,subprocess,sys
from collections import Counter,defaultdict
from functools import lru_cache
from pathlib import Path
w=Path(sys.argv[1]).resolve();out=w/'evidence/published';src=w/'worktree'
pre='7c5893b3d5198d2c5087dbb100e631dfe63a58bb:benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'
data=gzip.decompress(subprocess.check_output(['git','show',pre],cwd=src));pins=json.loads((src/'release/generated-license-evidence.json').read_text())
assert hashlib.sha256(data).hexdigest()==pins['symbol_map_sha256'] and len(data.splitlines())==pins['symbol_map_entries']
assert pins['guest_sha256'] in (src/'internal/generatedgo/guest_identity.go').read_text()
names=dict(line.split(':',1) for line in data.decode().splitlines())
@lru_cache(None)
def symbol(fn):
    match=re.search(r'/p\d+\.Fn(\d+)$',fn)
    if not match:return fn
    cpp=subprocess.check_output(['c++filt','-n',names[match[1]]],text=True).strip()
    return fn+' ('+cpp+')'
def ms(v):return round(v/1e6,5)
def table(name,rows):
    if not rows:return
    with (out/name).open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');wr.writeheader();wr.writerows(rows)
suites=[];samples=[];foreground=[];details=[]
for file in sorted((out/'runs').glob('*.gz')):
    run=json.loads(gzip.decompress(file.read_bytes()));meta={k:run[k] for k in ('kind','arm','block','position')}
    longest=0;tails=0
    for lane,win in run['windows'].items():
        a,b=win['start'],win['end'];dt=ms(b-a);is_tail=b-a>=400_000_000
        longest=max(longest,dt);tails+=is_tail
        spans=[];owned=[]
        for ev in run['dbs'][lane]['events'] or []:
            if ev['Selected']<=a or ev['Start']>=b:continue
            h=ev['Host'];op=ev.get('ClientOp')
            if not h or not op:continue
            assert a-2000<=op['Start']<=ev['Start']<=ev['Selected']<=op['End']<=b+2000
            wait=[symbol(x) for x in run['stacks'][ev['WaitStack']]]
            wake=[symbol(x) for x in run['stacks'][ev['WakeStack']]] if ev['WakeStack'] is not None else []
            def contains(stack,fn):return any(fn in s for s in stack)
            io_wake=ev['Branch']=='notify' and contains(wake,'write_io_callback(') and contains(wake,'AtomicNotify')
            matching=io_wake and contains(wait,'buf_page_get_gen(') and contains(wait,'::wait_and_lock()')
            stats_path=matching and contains(wait,'dict_stats_update_transient(')
            nq=ev['Notified'];cur=ev['Waker'];task=cur['Current']
            callback=cur['WriteAt'];inv=task['Invoked'];enq=task['Enqueued']
            queue_ok=bool(nq and task['Unique'] and 0<enq<=inv<=callback<=nq and contains(wake,'write_io_callback('))
            row=dict(**meta,lane=lane,sample_ms=dt,id=h['ID'],slot=h['Slot'],opcode=h['Op'],client_op=op['Op'],client_index=ev['ClientIndex'],
                     address=hex(ev['Address']),token=ev['Token'],reason=ev['Branch'],timeout_ns=ev['Timeout'],waiter_tid=ev['Waiting']['TID'],
                     waker_tid=cur['TID'] if wake else None,request_ms=ms(h['Resume']-h['Call']),wait_ms=ms(ev['Selected']-ev['Start']),
                     to_notify_ms=ms(nq-ev['Start']) if nq else None,after_notify_ms=ms(ev['Selected']-nq) if nq else None,
                     write_io_notify=io_wake,page_mutex_io=matching,stats_path=stats_path,unique_queue=queue_ok,same_argument=(task['Arg']==cur['WriteArg']) if queue_ok else None,
                     wait_to_enqueue_ms=ms(enq-ev['Start']) if queue_ok else None,queue_to_invoke_ms=ms(inv-enq) if queue_ok else None,
                     parent_task_ptr=task['ParentPtr'] if queue_ok else None,parent_enqueue_from_wait_ms=ms(task['ParentEnqueue']-ev['Start']) if queue_ok and task['ParentEnqueue'] else None,parent_invoke_to_enqueue_ms=ms(enq-task['ParentInvoke']) if queue_ok and task['ParentInvoke'] else None,simulated_aio_submit=bool(task['SubmitAIO']) if queue_ok else None,invoke_to_callback_ms=ms(callback-inv) if queue_ok else None,callback_to_notify_ms=ms(nq-callback) if queue_ok else None)
            foreground.append(row);owned.append(row);spans.append((max(a,ev['Start']),min(b,ev['Selected'])))
            if is_tail:details.append(dict(record=row,event=ev,wait_stack=wait,wake_stack=wake))
        duration=0;right=a
        for l,r in sorted(spans):
            duration+=max(0,r-max(right,l));right=max(right,r)
        io=sum(x['write_io_notify'] for x in owned)
        page=sum(x['page_mutex_io'] for x in owned)
        stats=sum(x['stats_path'] for x in owned)
        samples.append(dict(**meta,lane=lane,sample_ms=dt,above_400=is_tail,long_foreground=len(owned),write_io_waits=io,page_mutex_waits=page,stats_waits=stats,
                            foreground_wait_ms=ms(duration),share_pct=round(100*duration/(b-a),2)))
    suites.append(dict(**meta,suite_ms=run['suite_ms'],cpu_ms=round(run['cpu_ms'],3),max_sample_ms=longest,tail_samples=tails))
table('suites.csv',suites);table('samples.csv',samples);table('foreground.csv',foreground)
(out/'tail-details.json').write_text(json.dumps(details,indent=2)+'\n')
summary=[]
for arm in ('os','ring'):
    r=[v for v in suites if v['arm']==arm and v['kind']=='main']
    s=[v for v in samples if v['arm']==arm and v['kind']=='main']
    if not r:continue
    summary.append(dict(arm=arm,processes=len(r),samples=len(s),tail_suites=sum(v['tail_samples']>0 for v in r),tail_samples=sum(v['tail_samples'] for v in r),
                        write_io_tail_samples=sum(v['above_400'] and v['write_io_waits']>0 for v in s),
                        page_mutex_tail_samples=sum(v['above_400'] and v['page_mutex_waits']>0 for v in s),
                        stats_tail_samples=sum(v['above_400'] and v['stats_waits']>0 for v in s),
                        suite_median_ms=round(statistics.median(v['suite_ms'] for v in r),2),
                        max_sample_ms=max(v['sample_ms'] for v in s)))
table('summary.csv',summary)
