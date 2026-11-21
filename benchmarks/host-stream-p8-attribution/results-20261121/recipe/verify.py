"""Check coverage, pair order, monotonic phases, scheduler evidence and totals."""
import csv,json,math,statistics,sys,tarfile
from collections import Counter,defaultdict
from pathlib import Path
out=Path(sys.argv[1])
def rows(name):
    with (out/name).open() as f:return list(csv.DictReader(f))
runs=rows('suites.csv');samples=rows('samples.csv')
primary=[r for r in runs if r['series']=='primary']
assert len(primary)==96 and len(runs)==100 and len(samples)==2100
orders=defaultdict(list)
for r in primary:orders[int(r['block'])].append((int(r['position']),r['arm']))
assert len(orders)==24
assert all(len(v)==4 and len({s for _,s in v})==4 for v in orders.values())
for arm in ['raw-os','raw-ring','diag-os','diag-ring']:
    assert sorted(Counter(pos for order in orders.values() for pos,s in order if s==arm).values())==[6]*4
cases='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
coverage=None
with tarfile.open(out/'observations.tar.xz','r|xz') as tar:
    n=0
    for member in tar:
        n+=1
        r=json.load(tar.extractfile(member));s=r['suite']['spans']
        body=Counter((x['lane'],x['kind']) for x in s if x['kind'] in ('read','write','fork','sample'))
        if coverage is None:coverage=body
        assert body==coverage
        for i,case in enumerate(cases):
            assert sum(1 for lane,k in body if k in ('read','write') and lane.startswith('Test'+case+'/'))==(10 if i<5 else 4)
        if 'requests' in r:
            assert len(r['requests'])==21 and len(r['clients'])==21
            for reqs in r['requests'].values():
                assert all(all(row[4:]) and row[4:]==sorted(row[4:]) for row in reqs)
    assert n==len(runs)
for s in samples:
    if s['requests']:
        assigned=sum(float(s[k]) for k in ('admission','send_schedule','request_transfer','dispatch','worker','serialize','response_transfer','body','decode_notify','caller_resume','outside_call','overlap'))
        assert abs(assigned-float(s['elapsed_ms']))<0.001
slow=[s for s in samples if s['series']=='primary' and float(s['elapsed_ms'])>=400]
assert Counter(s['arm'] for s in slow)=={'raw-os':2,'raw-ring':1,'diag-os':1}
tails=json.loads((out/'tails.json').read_text())
sched=json.loads((out/'scheduler.json').read_text())
assert len(tails)==len(sched)==1
iv=tails[0]['intervals'][0];result=sched[0]
assert (iv['phase'],iv['client_op'],iv['id'])==('worker','prepare_order',result['id'])
assert abs(sum(result['states_ms'].values())-iv['interval_ms'])<0.1
ev=result['longest_wait']
assert 392<ev['duration_ms']<393
assert 'dict_stats_update_transient(' in str(ev['begin']['stacks'])
assert 'write_io_callback(' in str(ev['end']['stacks'])
assert 'timer_handler)' in str(result['creation_chain'])
print('PASS: 96 measured suites, four warmups, exact 70-case coverage, 21 sample lanes per suite, all named request phases, elapsed partition, decoded sleep/wake stacks and causal creation chain.')
