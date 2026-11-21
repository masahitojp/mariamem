"""Join each matched page's first I/O and its submitting doublewrite callback to a worker."""
import csv
import gzip
import json
import sys
from collections import Counter, namedtuple
from pathlib import Path

out = Path(sys.argv[1])
Event = namedtuple("Event", "at kind pool tid worker generation x y maintenance")
policy = {1:"queue_empty",2:"active_above_concurrency",3:"notify_one",4:"try_create",
          5:"thread_limit",6:"creation_throttle",7:"creation_pending",8:"thread_launch"}
def delta(a,b):
    return round((b-a)/1e6,5) if a is not None and b is not None else None
def unique(items):
    return items[0] if len(items)==1 else None

def resolve(events, enq, inv, ptr, control, completion=None):
    dispatch=unique([e for e in events if e.kind==13 and (e.generation,e.at,e.x,e.y)==(enq,inv,ptr,control)])
    if completion:
        # The completion invocation and worker are in the saved Waker.Current
        # for this exact control block. Kind 0 denotes this derived tuple.
        dispatch=Event(inv,0,completion['Pool'],completion['TID'],completion['Worker'],enq,ptr,control,0)
    if not dispatch:return {'matched':False}
    worker=dispatch.worker; pool=dispatch.pool
    scope=[e for e in events if e.pool==pool and enq<=e.at<=inv]
    take=unique([e for e in scope if e.kind==12 and e.x==ptr])
    policy_events=[e for e in scope if e.generation==enq and e.kind in policy]
    if not take or not policy_events:return {'matched':False}
    initial=policy_events[0]
    earlier=[e for e in scope if e.at<=take.at]
    target=[e for e in earlier if e.worker==take.worker]
    starts=[e for e in target if e.kind in (3,8)]
    # One specific signal/creation and exactly one subsequent return/start for
    # this worker. An available worker can also pick the task without either.
    action=starts[-1] if starts else None
    response=None;selected=None;notify=None
    if action:
        responses=[e for e in target if e.kind==(11 if action.kind==3 else 9) and e.at>=action.at and e.tid==take.tid]
        response=unique(responses)
        if action.kind==3 and response:
            ends=[e for e in target if e.kind==17 and e.y==1 and action.at<=e.at<=response.at]
            selected=unique(ends)
            if selected:
                notify=unique([e for e in target if e.kind==16 and e.x==selected.x and action.at<=e.at<=selected.at])
    release=action.at if action else None
    if response and action:
        assert enq<=release<=response.at<=take.at<=inv
    picks=[e for e in earlier if e.kind==12]
    gap_start=enq
    longest=(-1,None,None)
    for item in picks:
        if item.at-gap_start>longest[0]:longest=(item.at-gap_start,gap_start,item)
        gap_start=item.at
    length,left,right=longest
    gap_actions=[e for e in earlier if left<=e.at<=right.at and e.kind in (3,8)]
    recovery=gap_actions[0] if gap_actions else None
    recovery_response=None
    if recovery:
        kind=9 if recovery.kind==8 else 11
        recovery_response=next((e for e in earlier if recovery.at<=e.at<=right.at and e.kind==kind and
                               e.worker==recovery.worker==right.worker and e.tid==right.tid),None)
    schedule=dict(gap_ms=round(length/1e6,5),gap_start=left,gap_end=right.at,gap_first_take=list(right),
                  recovery=list(recovery) if recovery else None,recovery_response=list(recovery_response) if recovery_response else None,
                  recovery_is_maintenance=bool(recovery.maintenance) if recovery else None,
                  recovery_kind=policy[recovery.kind] if recovery else None,
                  enq_to_recovery_ms=delta(enq,recovery.at if recovery else None),
                  recovery_to_worker_ms=delta(recovery.at,recovery_response.at) if recovery_response else None,
                  restart_to_target_take_ms=delta(right.at,take.at),takes_to_target=len(picks))
    return dict(matched=True,worker=worker,worker_tid=take.tid,invoker_tid=dispatch.tid,**schedule,initial=policy[initial.kind],arg0=initial.x,arg1=initial.y,
                initial_steps=[policy[e.kind] for e in policy_events],enq_to_policy_ms=delta(enq,initial.at),
                action=policy[action.kind] if action else None,maintenance=bool(action.maintenance) if action else None,
                enq_to_action_ms=delta(enq,release),action_to_response_ms=delta(release,response.at if response else None),
                notify_to_selected_ms=delta(notify.at if notify else None,selected.at if selected else None),
                response_to_take_ms=delta(response.at if response else None,take.at),take_to_invoke_ms=delta(take.at,inv),
                maintenance_events=[list(e) for e in earlier if e.maintenance and e.kind in policy],
                initial_events=[list(e) for e in policy_events],action_event=list(action) if action else None,
                response_event=list(response) if response else None,take_event=list(take),invoke_event=list(dispatch))

def put(path,rows):
    if not rows:return
    with path.open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(rows)

records=[];all_slow=[];tails=Counter()
for path in sorted((out/'runs').glob('main-*-diag-*.gz')):
    r=json.loads(gzip.decompress(path.read_bytes()))
    for lane,db in r['dbs'].items():
        events=sorted(Event(*row) for row in db['worker_events'] or [])
        slow=[e for e in events if e.kind==13 and e.at-e.generation>=10_000_000]
        assert len(slow)==db['slow_first']
        if lane not in r['windows']:continue
        window=r['windows'][lane]
        is_tail=window['end']-window['start']>=400_000_000
        if is_tail:tails[r['arm']]+=1
        for w in db['events'] or []:
            if not(w.get('Host') and w.get('ClientOp') and w['Branch']=='notify'):continue
            a=w['Waker'];t=a['Current'];f=t['Flush']
            if not (f['Generation'] and f['Page']==a['CallbackPage'] and t['ParentUnique'] and t['Unique']
                    and t['Arg']==a['WriteArg']==f['Control'] and f['Offset']==f['Number']*int(r['settings'][lane]['after'][6])
                    and w['WakeStack'] is not None and any(s.endswith('.Fn17914') for s in r['stacks'][w['WakeStack']])):continue
            stages=[('page',t['ParentEnqueue'],t['ParentInvoke'],t['ParentPtr'],f['Control'])]
            if f['UpUnique'] and f['UpBatch'] and f['Buffered'] and f['FromWriteCallback']:
                candidates=[e for e in events if e.kind==18 and e.x==f['UpBatch']]
                match=unique([e for e in candidates if (e.generation,e.at,e.y)==(f['UpEnqueue'],f['UpInvoke'],f['UpControl'])])
                if match:
                    stages.append(('batch_callback_parent',f['UpEnqueue'],f['UpInvoke'],f['UpPtr'],f['UpControl']))
            if t['Invoked']-t['Enqueued']>=10_000_000:
                stages.append(('completion',t['Enqueued'],t['Invoked'],t['Ptr'],f['Control']))
            for role,enq,inv,ptr,control in stages:
                if inv-enq<10_000_000:continue
                joined=resolve(events,enq,inv,ptr,control,a if role=='completion' else None)
                blockers=[]
                if joined['matched'] and inv-enq>=100_000_000:
                    left=joined['gap_start'];right=joined['gap_end'];pool=joined['take_event'][2]
                    for hold in db['events'] or []:
                        actor=hold['Waiting']
                        if actor['Pool']!=pool or actor['CondWait']:continue
                        overlap=min(right,hold['Selected'])-max(left,hold['Start'])
                        if overlap<=0 or overlap<0.9*(right-left):continue
                        blockers.append(dict(tid=actor['TID'],worker=actor['Worker'],token=hold['Token'],overlap_ms=round(overlap/1e6,4),
                            stack=r['stacks'][hold['WaitStack']]))
                    joined['overlapping_worker_waits']=blockers
                records.append(dict(setting=r['arm'],period=r['period'],block=r['block'],lane=lane,tail=is_tail,role=role,enqueued=enq,
                                    queue_ms=delta(enq,inv),buffer_to_batch_submit_ms=delta(f['Buffered'],f['UpEnqueue']) if role=='batch_callback_parent' else None,
                                    **joined))
(out/'worker-details.json').write_text(json.dumps(records,indent=2)+'\n')
keys='setting period block lane tail role queue_ms matched initial gap_ms recovery_kind recovery_is_maintenance enq_to_recovery_ms recovery_to_worker_ms'.split()
put(out/'worker.csv',[{k:r.get(k) for k in keys} for r in records])
