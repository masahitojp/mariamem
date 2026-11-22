"""Compare initial hash capacities in one fixed test binary."""
from collections import Counter
from pathlib import Path
import gzip,json,os,re,subprocess,sys
root=Path.cwd();temp=root/'temp';out=root/'evidence'
cases='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
def run(mode,block,position,arm,n):
    name=f'{mode}-{block}-{position}-{arm}'
    d=temp/name;d.mkdir()
    env={key:os.environ[key] for key in ('HOME','PATH')}
    env.update(GOGC='100',GOMAXPROCS='8',TMPDIR=str(temp/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',COLLATION_RESERVE_EXPERIMENT=str(n),MODELCASE_TRACE=str(d/'suite.json'))
    if mode=='diag':env.update(FORK_GUEST_CLOCK='1',MARIAMEM_TIMING_DIR=str(d))
    test='^Test(CharsetReserveCatalog|MatchedSemantics)$' if mode=='oracle' else '^Test('+'|'.join(cases)+')$'
    p=subprocess.run(['/usr/bin/time','-l',temp/('observed.test' if mode=='diag' else 'perf.test'),'-test.v','-test.run='+test,'-test.parallel=1'],env=env,text=True,capture_output=True,timeout=120)
    if p.returncode or 'PASS' not in p.stdout or '--- SKIP:' in p.stdout:
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        raise RuntimeError(name+' '+(p.stdout+p.stderr)[-1500:])
    if mode=='oracle':
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        assert '--- PASS: TestCharsetReserveCatalog' in p.stdout and '--- PASS: TestMatchedSemantics' in p.stdout
        return re.search(r'CHARSET_ORACLE ([a-f0-9]{64})',p.stdout)[1]
    data={x.name:json.loads(x.read_bytes()) for x in d.glob('*.json')}
    suite=data['suite.json']
    count=Counter(s['kind'] for s in suite['spans'])
    assert all(count[k]==v for k,v in dict(read=50,write=20,close=21,fork=21,sample=21).items())
    data['measurement']=dict(rss_bytes=int(re.search(r'(\d+)\s+maximum resident set size',p.stderr)[1]),arm=arm,block=block,position=position,mode=mode)
    (out/'runs'/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    print(name,suite['elapsed_ms'],flush=True)
arms={'control':0,'reserve':1}
mode=sys.argv[1]
if mode=='oracle':
    a,b=[run('oracle',0,i,arm,n) for i,(arm,n) in enumerate(arms.items())]
    assert a==b,(a,b)
    print('Catalog digest',a,flush=True)
elif mode=='perf':
    for i,(a,n) in enumerate(arms.items()):run('warm',0,i,a,n)
    for b in range(1,7):
        order=('control','reserve','control') if b%2 else ('reserve','control','reserve')
        for i,a in enumerate(order):run(mode,b,i,a,arms[a])
else:
    assert mode=='diag'
    for b in range(1,5):
        order=('control','reserve') if b%2 else ('reserve','control')
        for i,a in enumerate(order):run(mode,b,i,a,arms[a])
