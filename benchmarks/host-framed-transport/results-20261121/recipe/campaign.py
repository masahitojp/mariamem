"""Bracket raw transport treatments with two OS measurements for each SQL condition."""
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

MODES=('os','input','output','both')
SQL=('ABC','BCA','CAB','CBA','BAC','ACB')
ORDERS=list(itertools.permutations(MODES[1:]))
TRACE=(('os','input','both','output'),('input','output','os','both'),('output','both','input','os'))
def jobs():
    for binary in ('raw','trace'):
        for sql in 'ABC':
            for mode in MODES: yield binary,0,sql,mode,1
    for b,seq in enumerate(SQL,1):
        for sql in seq:
            for mode in ('os1',*ORDERS[b-1],'os2'):yield 'raw',b,sql,mode,12
    for b,seq in enumerate(SQL[:3],1):
        for sql in seq:
            for mode in TRACE[b-1]:yield 'trace',b,sql,mode,12

def validate(trace,raw,sql):
    ids=set()
    assert len(trace)==len(raw)
    for db,(rows,cohort) in enumerate(zip(trace,raw)):
        assert len(rows)==100
        total=0
        for j,r in enumerate(rows):
            ts=r['T']
            assert (db,j)==(r['DB'],r['Ordinal']) and r['ID']>0 and (db,r['ID']) not in ids
            ids.add((db,r['ID']))
            assert len(ts)==21 and 0<ts[0] and all(a<=b for a,b in zip(ts,ts[1:]))
            assert j==0 or (rows[j-1]['T'][-1]<=ts[0] and rows[j-1]['ID']<r['ID'])
            assert r['TriggerCalls']==(2 if sql=='C' else 4) and 0<=r['TriggerNS']<=ts[9]-ts[8]
            assert r['RequestBytes']==97 and 214<=r['ResponseBytes']<=217
            total+=ts[-1]-ts[0]
        assert total<=cohort['raw_ns']

def verify_output(obs,sql,n):
    assert obs[0]['arm']==sql and len(obs[0]['registered'])==(4 if sql=='C' else 5)
    assert [(r['db'],r['inserts'],r['close']) for r in obs[1:]]==[(i,100,'pass') for i in range(n)]
    assert all(r['process_cpu_ns']>0 and r['raw_ns']>0 for r in obs[1:])

def main(w):
    t=w/'temp';p=w/'evidence/published';out=p/'runs';out.mkdir(exist_ok=True)
    env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'))
    meta=dict(host=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
              GOMAXPROCS=8,GOGC=100,concurrent_DBs=1,binaries={})
    for binary in ('raw','trace'):
        exe=t/binary
        meta['binaries'][binary]=dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            go=subprocess.check_output(['go','version','-m',exe],text=True))
    (p/'environment.json').write_text(json.dumps(meta,indent=2)+'\n')
    for binary,b,sql,mode,n in jobs():
        tag=f'{binary}-{b}-{sql}-{mode}';trial=out/tag;capture=t/'capture.json'
        args=[t/binary,'-arm',sql,'-forks',str(n)]
        realmode='os' if mode in ('os1','os2') else mode
        run=subprocess.run(args,text=True,capture_output=True,env=dict(env,MARIAMEM_BENCH_STREAM=realmode,TIMELINE_OUT=str(capture)),timeout=90)
        trial.with_suffix('.jsonl').write_text(run.stdout)
        if run.returncode:
            trial.with_suffix('.stderr').write_text(run.stderr)
            raise RuntimeError(tag+' '+run.stderr[:1000])
        obs=[json.loads(line) for line in run.stdout.splitlines()]
        verify_output(obs,sql,n)
        if binary=='trace':
            data=capture.read_bytes()
            trial.with_suffix('.json.gz').write_bytes(gzip.compress(data,compresslevel=1,mtime=0))
            validate(json.loads(data),obs[1:],sql)
        print(tag,'pass',flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
