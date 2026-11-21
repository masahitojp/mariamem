from pathlib import Path
import gzip,os,subprocess,json
from run import names
w=Path.cwd();t=w/'temp';e=w/'evidence'
for b in (1,2):
    diag=t/f'fork-{b}';diag.mkdir()
    trace=diag/'suite.json';env={k:os.environ[k] for k in ('PATH','HOME')};env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',MODELCASE_TRACE=str(trace),MARIAMEM_TIMING_DIR=str(diag))
    r=subprocess.run([t/'maria.test','-test.parallel=1','-test.v','-test.run=^Test('+'|'.join(names)+')$'],env=env,capture_output=True,text=True,timeout=120)
    assert r.returncode==0 and '--- SKIP' not in r.stdout and 'PASS' in r.stdout,r.stdout[-1000:]+r.stderr[-500:]
    data={p.name:json.loads(p.read_bytes()) for p in diag.glob('*.json')}
    assert len([d for d in data.values() if d.get('operation')=='fork'])==21
    assert sum(s['kind']=='fork' for s in data['suite.json']['spans'])==21
    (e/f'fork-{b}.json.gz').write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
