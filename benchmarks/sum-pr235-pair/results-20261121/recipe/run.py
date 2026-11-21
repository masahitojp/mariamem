"""Two warmups then six balanced, bracketed groups, each process serial."""
from pathlib import Path
import json,os,subprocess
w=Path.cwd();tmp=w/'temp';out=w/'evidence'/'runs'
env={k:os.environ[k] for k in ('PATH','HOME')}
env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(tmp/'gotmp'))
jobs=[('warm-'+arm,arm,1) for arm in ('os','ring')]
for b in range(1,7):
    order=('os','ring','os') if b%2 else ('ring','os','ring')
    jobs.extend((f'{b}-{i}-{arm}',arm,12) for i,arm in enumerate(order,1))
registered=None
for tag,arm,n in jobs:
    path=out/(tag+'.jsonl')
    assert not path.exists()
    r=subprocess.run([tmp/arm,'-arm','A','-forks',str(n)],env=env,text=True,capture_output=True,timeout=120)
    path.write_text(r.stdout)
    if r.returncode:
        (out/(tag+'.stderr')).write_text(r.stderr)
        raise RuntimeError(tag+' '+r.stderr[-1000:])
    header,*rows=map(json.loads,r.stdout.splitlines())
    assert header['arm']=='A' and len(header['registered'])==5
    if registered is None:registered=header['registered']
    assert registered==header['registered'] and 'SUM(' in registered['order_items_total_insert']
    assert len(rows)==n
    for i,row in enumerate(rows):
        assert row['db']==i and row['raw_ns']>0 and row['inserts']==100 and row['close']=='pass'
    print(tag,'PASS',flush=True)
