"""Run paired checked 256 KiB responses and matched P1/P8 modelcases on macOS."""
import csv
import hashlib
import json
import os
import re
import resource
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

w = Path(sys.argv[1]).resolve()
e = w / 'evidence'
t = w / 'temp'
sys.path.insert(0,str(w/'worktree/scripts'))
from experiment_disk import DiskGuard
guard = DiskGuard(w, min_free_gib=8, budget_gib=8)
guard.check()
base = {'GOMAXPROCS':'8', 'GOGC':'100', 'MODELCASE_MATCHED':'1', 'MARIA_AUDIT_OF':'1',
        'REVENUE_PREAGG':'1', 'MARIA_ASYNC_CLOSE':'0', 'SKIP_READ_BODY':'0', 'TRANSPORT_DIAG':'0'}
env = {k:os.environ[k] for k in ('PATH','HOME') if k in os.environ}
env.update(base, TMPDIR=str(t/'gotmp'))
tail_only = sys.argv[2:] == ['p8-tail']
scenarios = ['p8'] if tail_only else ['large','p1','p8']
prefix = 'tail-' if tail_only else ''
arms = ['baseline','candidate']
tests = '^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$'
rows = []
binaries={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for a in arms for p in [t/(a+'.test'),t/('model-'+a+'.test')]}
(e/'binary-sha256.json').write_text(json.dumps(binaries,indent=2)+'\n')

def run(scenario, arm, index):
    label = f'{prefix}{scenario}-{arm}-{index}'
    bench = scenario=='large'
    exe = t/((arm if bench else 'model-'+arm)+'.test')
    trace = t/(label+'.json')
    if scenario=='semantics':
        args = ['-test.run=^TestMatchedSemantics$', '-test.v']
    elif bench:
        args = ['-test.run=^$', '-test.bench=^BenchmarkLargeResponseBatch$', '-test.benchtime=1x', '-test.count=1']
    else:
        args = ['-test.run='+tests, '-test.parallel='+scenario[1:], '-test.count=1']
    prior = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic_ns()
    log = subprocess.check_output([exe,*args,'-test.timeout=90s'],env=dict(env,MODELCASE_TRACE=str(trace)),text=True,stderr=subprocess.STDOUT)
    elapsed = (time.monotonic_ns()-start)/1e6
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (t/(label+'.log')).write_text(log)
    cpu = (after.ru_utime-prior.ru_utime + after.ru_stime-prior.ru_stime)*1000
    if scenario=='semantics':
        assert '--- PASS: TestMatchedSemantics' in log
        return
    if bench:
        match = re.search(r'BenchmarkLargeResponseBatch-\d+\s+1\s+(\d+) ns/op\s+(\d+) cpu-ns/op',log)
        assert match,log
        wall_ms, cpu_ms = [int(s)/1e6 for s in match.groups()]
    else:
        tr=json.loads(trace.read_text());counts=Counter(s['kind'] for s in tr['spans'])
        assert all(counts[k]==v for k,v in dict(read=50,write=20,sample=21,fork=21).items()),counts
        wall_ms,cpu_ms = tr['elapsed_ms'],cpu
    if index:
        rows.append(dict(scenario=scenario,arm=arm,block=index,elapsed_ms=wall_ms,cpu_ms=round(cpu_ms,4),process_ms=round(elapsed,4)))
    print(label,round(wall_ms,2),round(cpu_ms,2),flush=True)

if not tail_only:
    for arm in arms: run('semantics',arm,0)
for scenario in scenarios:
    for arm in arms: run(scenario,arm,0)
for i in range(1,7):
    guard.check()
    for scenario in scenarios:
        for arm in (arms if (i%2==1) != tail_only else arms[::-1]): run(scenario,arm,i)
with (e/(prefix+'measurements.csv')).open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
for scenario in scenarios:
    r=[v for v in rows if v['scenario']==scenario]
    for key in ('elapsed_ms','cpu_ms'):
        a=[x[key] for x in r if x['arm']=='baseline']
        b=[x[key] for x in r if x['arm']=='candidate']
        delta=[100*(y/x-1) for x,y in zip(a,b)]
        print(scenario,key,'median',round(statistics.median(a),2),round(statistics.median(b),2),'paired%',round(statistics.median(delta),2),'lower',sum(d<0 for d in delta),'of',len(delta),flush=True)
