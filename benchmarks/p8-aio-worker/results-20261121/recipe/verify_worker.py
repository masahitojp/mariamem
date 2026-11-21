"""Validate the reported eleven long chains against raw worker and futex events."""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

out=Path(sys.argv[1])
chains=[s for s in json.loads((out/'worker-details.json').read_text()) if s['queue_ms']>=100]
tails=set()
raw={}
for p in (out/'runs').glob('main-*.gz'):
    run=json.loads(gzip.decompress(p.read_bytes()))
    key=(run['arm'],run['block'])
    assert key not in raw
    raw[key]=p
    for lane,win in run['windows'].items():
        if win['end']-win['start']>=400_000_000:
            tails.add((*key,lane))
assert len(tails)==len(chains)==11
assert {(s['setting'],s['block'],s['lane']) for s in chains}==tails
assert Counter(s['role'] for s in chains)=={'page':3,'batch_callback_parent':7,'completion':1}
for s in chains:
    run=json.loads(gzip.decompress(raw[s['setting'],s['block']].read_bytes()))
    db=run['dbs'][s['lane']]
    events=sorted(db['worker_events'])
    assert [e[1] for e in s['initial_events']]==[4,7]
    assert all(e in events and e[5]==s['enqueued'] for e in s['initial_events'])
    launch,start,first=s['recovery'],s['recovery_response'],s['gap_first_take']
    assert all(e in events for e in [launch,start,first,s['take_event']])
    assert (launch[1],launch[8],start[1],first[1])==(8,1,9,12)
    assert launch[2]==start[2]==first[2] and launch[4]==start[4]==first[4] and start[3]==first[3]
    assert s['enqueued']<=launch[0]<=start[0]<=first[0]<=s['take_event'][0]<=s['invoke_event'][0]
    assert not any(e[2]==first[2] and e[1]==12 and s['gap_start']<e[0]<s['gap_end'] for e in events)
    roles=set()
    for h in s['overlapping_worker_waits']:
        w=next(e for e in db['events'] if e['Token']==h['token'])
        who=w['Waiting']
        assert who['Pool']==first[2] and who['Worker']==h['worker'] and not who['CondWait']
        overlap=min(s['gap_end'],w['Selected'])-max(s['gap_start'],w['Start'])
        assert overlap/(s['gap_end']-s['gap_start'])>.99
        stack=run['stacks'][w['WaitStack']]
        roles.update(k for k in ('Fn18241','Fn18244') if any(fr.endswith('.'+k) for fr in stack))
    assert roles=={'Fn18241','Fn18244'}
print('PASS: All 11 long loads map to one slow queue stage each, 11 pending-creation branches, 11 maintenance launches with matching worker entry and first dequeue. Both purge callbacks parked during over 99% of each longest no-dequeue interval.')
