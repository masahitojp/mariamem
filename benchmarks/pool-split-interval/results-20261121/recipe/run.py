"""Run balanced three-arm comparisons serially. Save complete spans for replay."""
from collections import Counter
from itertools import permutations
from pathlib import Path
import gzip
import json
import os
import re
import resource
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
phase = sys.argv[2]
temp = root / 'temp'
out = root / 'evidence/study'
configs = {'current': (400, 4000), 'short': (50, 500), 'split': (50, 4000)}
orders = list(permutations(configs))
cases = 'GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()

def invoke(binary, arm, parallel, args, label, extra=None):
    active, idle = configs[arm]
    env = {k: os.environ[k] for k in ('HOME', 'PATH')}
    env.update(TMPDIR=str(temp/'gotmp'), GOGC='100', GOMAXPROCS=str(parallel),
               MODELCASE_MATCHED='1', REVENUE_PREAGG='1', MARIA_AUDIT_OF='1', MARIA_ASYNC_CLOSE='0',
               SKIP_READ_BODY='0', TRANSPORT_DIAG='0', POOL_PERIOD_MS=str(active),
               POOL_SPLIT=str(int(arm=='split')), MODELCASE_TRACE=str(temp/'suite.json'))
    env.update(extra or {})
    def cpu():
        r = resource.getrusage(resource.RUSAGE_CHILDREN)
        return r.ru_utime + r.ru_stime
    before = cpu()
    p = subprocess.run([temp/(binary+'-ring.test'), *args], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=190)
    cost = 1000*(cpu()-before)
    if p.returncode or '--- SKIP:' in p.stdout:
        (out/('failed-'+label+'.log')).write_text(p.stdout)
        raise RuntimeError(label+' '+p.stdout[-2400:])
    return p.stdout, cost

def run_suite(arm, parallel, block, position, kind):
    label = f'p{parallel}-{kind}-{block}-{position}-{arm}'
    pattern = '^TestMatchedSemantics$' if kind == 'semantics' else '^Test('+'|'.join(cases)+')$'
    log, cost = invoke('raw', arm, parallel,
                       ['-test.run='+pattern, f'-test.parallel={parallel}', '-test.v', '-test.timeout=60s'], label)
    expected = '2' if kind == 'semantics' else '22'
    assert re.findall(r'^POOL_PERIOD (\d+) (\d+)$',log,re.M)==[(str(configs[arm][0]), expected)]
    trace = json.loads((temp/'suite.json').read_bytes())
    spans = trace['spans']
    if kind == 'semantics':
        assert '--- PASS: TestMatchedSemantics ' in log
    else:
        counts = Counter(s['kind'] for s in spans)
        for key,n in [('sample',21),('fork',21),('read',50),('write',20)]:
            assert counts[key]==n
        for i, case in enumerate(cases):
            assert sum(s['kind'] in ('read','write') and s['lane'].startswith('Test'+case+'/') for s in spans)==(10 if i<5 else 4)
    return dict(arm=arm, parallel=parallel, block=block, position=position, kind=kind,
                armed=int(expected), cpu_ms=cost, trace=trace)

def run_hold(arm, block, position, pilot):
    label = ('pilot' if pilot else 'idle')+f'-{block}-{position}-{arm}'
    result = temp/(label+'.json')
    invoke('idle', arm, 8, ['-test.run=^$', '-test.timeout=180s'], label,
           dict(IDLE_DBS='8', IDLE_PILOT=str(int(pilot)), IDLE_REVERSE=str(int(block==2)), IDLE_REPORT=str(result)))
    r = json.loads(result.read_bytes())
    assert (r['Period'],r['IdleMS'])==configs[arm] and r['Armed']==9
    assert len(r['After'])==8 and all(v==[40,100,1888173,1888173] for v in r['After'])
    assert [v['ID'] for v in r['Wakes']]==list(range(2,10)) and sum(v['Write'] for v in r['Wakes'])==4
    assert all(abs(v['Seconds']-sec)<1 for v,sec in zip(r['Readings'], [0,1,2,3] if pilot else [0,30,70,120]))
    if not pilot:
        assert r['LowWrites']>=1 and r['Readings'][-1]['SetLow']>=1
    r.update(arm=arm, block=block, position=position)
    (out/(label+'.json')).write_text(json.dumps(r, indent=2)+'\n')
    print(label,'PASS',flush=True)

if phase in ('p1','p8'):
    parallel = int(phase[1:])
    with gzip.open(out/(phase+'-spans.jsonl.gz'), 'xt', compresslevel=5) as stream:
        def record(*args):
            row = run_suite(*args)
            stream.write(json.dumps(row,separators=(',',':'))+'\n')
            stream.flush()
        for arm in configs:
            for kind in ('semantics','warm'):
                record(arm, parallel, 0, 0, kind)
        for block in range(1, (48 if parallel==1 else 96)+1):
            for pos, arm in enumerate(orders[(block-1)%len(orders)]):
                record(arm, parallel, block, pos, 'main')
            print(phase,block,'PASS',flush=True)
elif phase in ('idle','pilot'):
    plan = [list(configs)] if phase=='pilot' else [list(configs), list(reversed(configs))]
    for block, order in enumerate(plan, 1):
        for pos, arm in enumerate(order):
            run_hold(arm, block, pos, phase=='pilot')
else:
    raise ValueError(phase)
