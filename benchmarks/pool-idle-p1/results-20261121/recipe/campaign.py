"""Serial local process measurements for P1 modelcase and disconnected idle forks."""
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys

w=Path(sys.argv[1]).resolve()
stage=sys.argv[2]
t=w/'temp'
out=w/'evidence/study'
(out/'runs').mkdir(exist_ok=True)
cases='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
def process(mode,period,env_args,args,label,timeout):
    env={k:os.environ[k] for k in ('HOME','PATH') if k in os.environ}
    env.update(TMPDIR=str(t/'gotmp'),GOGC='100',GOMAXPROCS='1' if mode=='raw' else '8',
               MODELCASE_MATCHED='1',REVENUE_PREAGG='1',MARIA_AUDIT_OF='1',MARIA_ASYNC_CLOSE='0',
               SKIP_READ_BODY='0',TRANSPORT_DIAG='0',POOL_PERIOD_MS=str(period),
               MODELCASE_TRACE=str(t/'suite.json'))
    env.update(env_args)
    start=resource.getrusage(resource.RUSAGE_CHILDREN)
    p=subprocess.run([t/(mode+'-ring.test'),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    end=resource.getrusage(resource.RUSAGE_CHILDREN)
    log=p.stdout.decode(errors='replace')
    if p.returncode or '--- SKIP' in log:
        (out/('failed-'+label+'.log')).write_text(log)
        raise RuntimeError(label+' '+log[-1800:])
    return log,1000*(end.ru_utime+end.ru_stime-start.ru_utime-start.ru_stime)
def run_idle(period,n,block,position,pilot=False):
    label=('pilot' if pilot else 'idle')+f'-{block:02}-{position}-{n}-{period}'
    result=t/('data-'+label+'.json')
    process('idle',period,dict(IDLE_DBS=str(n),IDLE_REPORT=str(result),IDLE_PILOT=str(int(pilot))),
            ['-test.run=^$','-test.timeout=200s'],label,200)
    r=json.loads(result.read_text())
    assert r['Armed']==n+1 and r['DBs']==n and len(r['After'])==n and r['Period']==period
    assert all(v==r['Expected'] for v in r['After']) and r['Expected'][0:2]==[40,100]
    now=[v['Seconds'] for v in r['Readings']]
    times=[0,1,2,3] if pilot else [0,30,70,120]
    assert len(now)==4 and all(abs(x-y)<1 for x,y in zip(now,times)),(label,now)
    r.update(block=block,position=position)
    (out/'runs'/(label+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    print(label,'PASS',round(now[-1],2),flush=True)
def run_p1(period,block,position,kind):
    label=f'p1-{kind}-{block:02}-{position}-{period}'
    pattern='^TestMatchedSemantics$' if kind=='meaning' else '^Test('+'|'.join(cases)+')$'
    log,cpu=process('raw',period,{},['-test.run='+pattern,'-test.parallel=1','-test.v','-test.timeout=60s'],label,75)
    witness=re.findall(r'^POOL_PERIOD (\d+) (\d+)$',log,re.M)
    assert witness==[(str(period),'2' if kind=='meaning' else '22')],(label,witness)
    if kind=='meaning':
        assert '--- PASS: TestMatchedSemantics ' in log
    else:
        s=json.loads((t/'suite.json').read_text())
        counts=Counter(v['kind'] for v in s['spans'])
        assert all(counts[k]==n for k,n in dict(read=50,write=20,sample=21,fork=21).items())
        for i,name in enumerate(cases):
            assert sum(x['kind'] in ('read','write') and x['lane'].startswith('Test'+name+'/') for x in s['spans'])==(10 if i<5 else 4)
        loads={v['lane']:round(v['end_ms']-v['start_ms'],5) for v in s['spans'] if v['kind']=='sample'}
        assert len(loads)==21
        row=dict(period=period,block=block,position=position,kind=kind,wall_ms=s['elapsed_ms'],cpu_ms=cpu,loads=loads,counts=dict(counts),armed=22)
        (out/'runs'/(label+'.json')).write_text(json.dumps(row,separators=(',',':'))+'\n')
    print(label,'PASS',flush=True)
if stage=='idle-pilot':
    for p,n in [(400,1),(50,8)]:run_idle(p,n,0,0,True)
elif stage=='idle':
    order=[(400,1),(50,1),(50,8),(400,8)]
    for b,seq in enumerate((order,order[::-1]),1):
        for pos,(p,n) in enumerate(seq):run_idle(p,n,b,pos)
elif stage=='p1':
    for p in (400,50):
        run_p1(p,0,0,'meaning');run_p1(p,0,0,'warm')
    for b in range(1,49):
        for pos,p in enumerate((400,50) if b%2 else (50,400)):run_p1(p,b,pos,'main')
else:raise ValueError(stage)
