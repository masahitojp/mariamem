"""Reduce counter observations using request/SQL intervals and same-DB wait unions."""
import collections
import json
from pathlib import Path
import sys

def union(spans):
    total=0
    end=-1
    for start,stop in sorted(spans):
        if stop>max(start,end): total+=stop-max(start,end)
        end=max(end,stop)
    return total

results=Path(sys.argv[1])
output=[]
for path in sorted(results.glob('[123]-*-events.json')):
    run=path.name.split('-events')[0]
    data=json.loads(path.read_bytes())
    requests=data['Requests']
    assert len(requests)==100
    waits=data['Waits'] or []
    outside=[w for w in waits if w['Agent']=='outside target SQL']
    on=[w for w in waits if w['Agent']=='target']
    counters=collections.Counter(); trigger=collections.Counter(); times=collections.Counter()
    attached=collections.defaultdict(list)
    for w in on: attached[(w['DB'],w['Insert'])].append(w)
    stats=collections.Counter()
    for i,r in enumerate(requests):
        assert (r['DB'],r['Insert'],r['SQLCalls'],r['Depth'])==(0,i,1,0)
        lo,hi=r['SQLBegin'],r['SQLEnd']
        assert r['ClientBegin']<=lo<=hi<=r['ClientEnd']
        foreground=attached[(0,i)]
        assert all(w['ThreadGroup']==r['ThreadGroup'] and lo<=w['Begin']<=w['End']<=hi for w in foreground)
        assert len(foreground)==r['Calls'].get('AtomicWait',0)
        spans=[(w['Begin'],w['End']) for w in foreground]
        background=[(max(lo,w['Begin']),min(hi,w['End'])) for w in outside
                    if w['ThreadGroup']==r['ThreadGroup'] and w['Begin']<hi and w['End']>lo]
        stats['client_elapsed_ns']+=r['ClientEnd']-r['ClientBegin']
        stats['sql_elapsed_ns']+=hi-lo
        stats['fg_wait_union_ns']+=union(spans)
        stats['bg_overlap_sql_union_ns']+=union(background)
        stats['fg_bg_overlap_ns']+=union(spans)+union(background)-union(spans+background)
        parked=[(w['ParkBegin'],w['ParkEnd']) for w in foreground if w['ParkBegin']]
        assert all(lo<=b<=e<=hi for b,e in parked)
        stats['fg_select_union_ns']+=union(parked)
        stats['requests_with_select']+=bool(parked)
        stats['requests_with_wait']+=bool(foreground)
        stats['fg_wait_return_1_value_mismatch']+=sum(w['Result']==1 for w in foreground)
        counters.update(r['Calls']); trigger.update(r['TriggerCalls']); times.update(r['TimesNS'])
    assert sum(r['Calls'].get('AtomicWait',0) for r in requests)==len(on)
    output.append(dict(run=run,inserts=len(requests),calls=counters,trigger_calls=trigger,times_ns=times,
                       interval_totals=stats,all_outside_SQL_completed_waits=len(outside),
                       heap_stack_bytes=data['HeapStackBytes']))
(results/'counters.json').write_text(json.dumps(output,indent=2)+'\n')
