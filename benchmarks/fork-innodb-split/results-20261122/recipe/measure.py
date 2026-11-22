from pathlib import Path
import gzip,os,subprocess,json
from run import names
w=Path.cwd();t=w/'temp';e=w/'evidence'
import itertools
arms=('normal','host','guest')
orders=list(itertools.permutations(arms))[:2]+list(itertools.permutations(arms))[4:]
for b,arm in [(b,a) for b,order in enumerate(orders,1) for a in order]:
    diag=t/f'{arm}-{b}';diag.mkdir()
    trace=diag/'suite.json';env={k:os.environ[k] for k in ('PATH','HOME')};env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',MODELCASE_TRACE=str(trace),MARIAMEM_TIMING_DIR=str(diag))
    if arm=='normal':env.pop('MARIAMEM_TIMING_DIR')
    env['FORK_GUEST_CLOCK']='1' if arm=='guest' else '0'
    r=subprocess.run([t/('maria.test' if arm=='normal' else 'observed.test'),'-test.parallel=1','-test.v','-test.run=^Test('+'|'.join(names)+')$'],env=env,capture_output=True,text=True,timeout=120)
    assert r.returncode==0 and '--- SKIP' not in r.stdout and 'PASS' in r.stdout,r.stdout[-1000:]+r.stderr[-500:]
    data={p.name:json.loads(p.read_bytes()) for p in diag.glob('*.json')}
    assert len([d for d in data.values() if d.get('operation')=='fork'])==(0 if arm=='normal' else 21)
    from collections import Counter
    counts=Counter(s['kind'] for s in data['suite.json']['spans'])
    assert all(counts[k]==v for k,v in dict(fork=21,read=50,write=20,sample=21,close=21).items())
    print(arm,b,data['suite.json']['elapsed_ms'],flush=True)
    (e/'runs'/f'{arm}-{b}.json.gz').write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
