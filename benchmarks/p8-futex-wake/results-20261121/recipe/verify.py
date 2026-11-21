"""Independent invariants for the saved P8 observations and joined attributions."""
import csv,gzip,json,sys
from collections import Counter
from pathlib import Path
out=Path(sys.argv[1])
def table(name):
    with (out/name).open() as f:return list(csv.DictReader(f))
rows=table('suites.csv');main=[r for r in rows if r['kind']=='main']
assert len(rows)==194 and len(main)==192
assert Counter(r['arm'] for r in main)==dict(os=96,ring=96)
for i in range(1,97):
    pair=sorted((r for r in main if int(r['block'])==i),key=lambda r:int(r['position']))
    assert [r['arm'] for r in pair]==(['os','ring'] if i%2 else ['ring','os'])
samples=table('samples.csv')
assert len(samples)==194*21
details=json.loads((out/'tail-details.json').read_text())
for row in rows:
    case=[s for s in samples if (s['arm'],s['block'],s['kind'])==(row['arm'],row['block'],row['kind'])]
    assert len(case)==len({s['lane'] for s in case})==21
    assert sum(s['above_400']=='True' for s in case)==int(row['tail_samples'])
tails=[s for s in samples if s['kind']=='main' and s['above_400']=='True']
def lane_key(v):return (v['arm'],int(v['block']),v['lane'])
assert len(tails)==8 and all(s['arm']=='ring' for s in tails)
assert Counter(map(lane_key,tails))==Counter(lane_key(d['record']) for d in details)
assert all(d['record']['write_io_notify'] and d['record']['unique_queue'] and d['record']['same_argument'] for d in details)
assert sum(d['record']['page_mutex_io'] for d in details)==7
assert sum(d['record']['stats_path'] for d in details)==3
for d in details:
    v,e=d['record'],d['event']
    assert v['sample_ms']>=400 and e['Waiting']['Request']==v['id']==e['Host']['ID']
    assert e['Waiting']['TID']==v['waiter_tid'] and e['Host']['Slot']==e['Host']['ReplySlot']
    assert e['ClientOp']['Start']<=e['Start']<=e['Selected']<=e['ClientOp']['End']
    assert e['Host']['Call']<=e['Start']<=e['Selected']<=e['Host']['Resume']
    if v['write_io_notify']:
        assert e['Branch']=='notify' and 'write_io_callback(' in str(d['wake_stack'])
        assert e['Start']<=e['Notified']<=e['Selected']
    if v['unique_queue']:
        terms=['wait_to_enqueue_ms','queue_to_invoke_ms','invoke_to_callback_ms','callback_to_notify_ms','after_notify_ms']
        assert abs(sum(v[k] for k in terms)-v['wait_ms'])<0.0001
for f in (out/'runs').glob('*.gz'):
    r=json.loads(gzip.decompress(f.read_bytes()))
    assert all(r['counts'][k]==n for k,n in dict(read=50,write=20,sample=21,fork=21).items())
    for db in r['dbs'].values():
        evs=db['events'] or []
        assert len({e['Token'] for e in evs})==len(evs) and all(0<e['Token']<=db['parked'] for e in evs)
        for e in evs:
            assert e['Selected']>=e['Start']+100_000_000 and e['WaitStack'] is not None
            if e['Branch']=='timeout':assert e['Timeout']>0
assert len(list((out/'runs').glob('*.gz')))==194
print('PASS: 96 complete AB/BA pairs and two warmups, 21 checked sample lanes per suite, unique waiter tokens, actual selected branches, matched host requests and disjoint queue intervals.')
