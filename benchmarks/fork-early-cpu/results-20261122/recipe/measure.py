"""Collect timing controls and independent CPU samples from the same fixture."""
from pathlib import Path
from collections import Counter
import gzip,json,os,subprocess,sys

w=Path.cwd();tmp=w/'temp';out=w/'evidence'
names='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
def measure(arm,b,profile=False):
    tag=f'{arm}-{b:02d}'
    d=tmp/tag
    d.mkdir()
    env={k:os.environ[k] for k in ('PATH','HOME')}
    env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(tmp/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',MARIAMEM_TIMING_DIR=str(d),MODELCASE_TRACE=str(d/'suite.json'),FORK_GUEST_CLOCK='0' if arm=='host' else '1',FORK_EARLY_PROFILE='1' if profile else '0')
    args=[tmp/'observed.test','-test.parallel=1','-test.run=^Test('+'|'.join(names)+')$','-test.v']
    if profile:args+=['-test.cpuprofile='+str(out/'profiles'/(tag+'.pprof')),'-test.outputdir='+str(d)]
    r=subprocess.run(args,env=env,text=True,capture_output=True,timeout=120)
    if r.returncode or 'PASS' not in r.stdout or '--- SKIP' in r.stdout:
        (out/(tag+'.log')).write_text(r.stdout+r.stderr)
        raise RuntimeError(tag)
    data={x.name:json.loads(x.read_bytes()) for x in d.glob('*.json')}
    c=Counter(s['kind'] for s in data['suite.json']['spans'])
    assert all(c[k]==v for k,v in dict(read=50,write=20,close=21,fork=21,sample=21).items())
    assert sum(x.get('operation')=='fork' for x in data.values())==21
    if profile:
        (out/'profiles'/(tag+'.json')).write_text(json.dumps(dict(suite_ms=data['suite.json']['elapsed_ms'],counts=c))+'\n')
    else:
        (out/'runs'/(tag+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    print(tag,data['suite.json']['elapsed_ms'],flush=True)
if sys.argv[1]=='times':
    for b in range(1,5):
        for arm in (('host','detail') if b%2 else ('detail','host')):measure(arm,b)
else:
    assert sys.argv[1]=='profiles'
    for b in range(1,25):measure('profile',b,True)
