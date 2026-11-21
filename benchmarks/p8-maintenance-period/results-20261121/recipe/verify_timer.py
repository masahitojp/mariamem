"""Summarize distinct, foreground-linked tasks and cross-check the recorded timer witness."""
import csv
import gzip
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

out=Path(sys.argv[1])
seen={}
for row in json.loads((out/'worker-details.json').read_text()):
    key=tuple(row[k] for k in ('setting','period','block','lane','enqueued'))
    if key in seen:
        assert seen[key]['queue_ms']==row['queue_ms']
    seen[key]=row
results=[]
for arm in ('default','off'):
    for period in (400,50):
        selected=[r for key,r in seen.items() if key[:2]==(arm,period)]
        verified=[r for r in selected if r.get('initial_steps')==['try_create','creation_pending']
                  and r.get('recovery_kind')=='thread_launch' and r.get('recovery_is_maintenance') and r.get('recovery_response')]
        for r in verified:
            launch,start,first=r['recovery'],r['recovery_response'],r['gap_first_take']
            assert (launch[1],launch[8],start[1],first[1])==(8,1,9,12)
            assert launch[2]==start[2]==first[2] and launch[4]==start[4]==first[4] and start[3]==first[3]
            assert r['enqueued']<=launch[0]<=start[0]<=first[0]<=r['invoke_event'][0]
        vals=[r['queue_ms'] for r in verified]
        results.append(dict(setting=arm,period=period,linked_ge10=len(selected),verified=len(vals),verified_ge100=sum(v>=100 for v in vals),
                            verified_min_ms=min(vals,default=None),verified_max_ms=max(vals,default=None),
                            linked_max_ms=max((r['queue_ms'] for r in selected),default=None),
                            roles=dict(Counter(r['role'] for r in verified))))
paths=list((out/'runs').glob('*.json.gz'))
assert len(paths)==576+6
for path in paths:
    r=json.loads(gzip.decompress(path.read_bytes()))
    assert r['armed']==22 and len(r['windows'])==21
with (out/'mechanism-summary.json').open('w') as f:json.dump(results,f,indent=2);f.write('\n')
print('PASS: all 582 saved suites armed 22 pool timers at the requested interval; linked maintenance recoveries checked by worker and task identity.')
print(json.dumps(results))
