from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

w=Path(sys.argv[1]).resolve(); t=w/'temp'
out=w/'evidence/published'
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'))
metadata=dict(host=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
              gomaxprocs=8,gogc=100,processes_at_once=1,binaries={})
for arm in ('base','shim'):
    b=t/arm
    metadata['binaries'][arm]=dict(bytes=b.stat().st_size,sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
        go=subprocess.check_output(['go','version','-m',b],text=True))
(out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
def run(block,sql,arm,forks,log):
    load_before=os.getloadavg()
    start=time.monotonic()
    result=subprocess.run([t/arm,'-arm',sql,'-forks',str(forks)],env=env,capture_output=True,text=True)
    if result.returncode:
        print(result.stderr,flush=True)
        raise RuntimeError((block,sql,arm,result.returncode))
    rows=[json.loads(s) for s in result.stdout.splitlines()]
    assert rows[0]['arm']==sql and len(rows[0]['registered'])=={'A':5,'B':5,'C':4}[sql]
    assert [(r['db'],r['inserts'],r['close']) for r in rows[1:]]==[(i,100,'pass') for i in range(forks)]
    json.dump(dict(block=block,sql=sql,arm=arm,elapsed_s=time.monotonic()-start,load_before=load_before,load_after=os.getloadavg(),rows=rows),log)
    log.write('\n');log.flush()
    print(block,sql,arm,'pass',flush=True)
with (out/'observations.jsonl').open('w') as log:
    for arm in ('base','shim'):
        for sql in 'ABC': run(0,sql,arm,1,log)
    for i,order in enumerate(('ABC','BCA','CAB')*2,1):
        for sql in order:
            for arm in (('base','shim') if i%2 else ('shim','base')): run(i,sql,arm,43,log)
