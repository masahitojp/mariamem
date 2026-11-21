"""Three rotated P1 blocks. Each fresh DB uses the published input and oracles."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

def tracecheck(groups,raw,sql):
    assert len(groups)==len(raw)
    ids=set()
    for db,(rows,cohort) in enumerate(zip(groups,raw)):
        assert len(rows)==100
        span=0
        for i,r in enumerate(rows):
            ts=r['T']
            assert (db,i)==(r['DB'],r['Ordinal']) and r['ID']>0 and (db,r['ID']) not in ids
            ids.add((db,r['ID']))
            assert len(ts)==21 and ts[0]>0 and all(a<=b for a,b in zip(ts,ts[1:]))
            assert i==0 or (rows[i-1]['T'][-1]<=ts[0] and rows[i-1]['ID']<r['ID'])
            assert r['TriggerCalls']==(2 if sql=='C' else 4)
            assert 0<=r['TriggerNS']<=ts[9]-ts[8]
            assert sum(b-a for a,b in zip(ts,ts[1:]))==ts[-1]-ts[0]
            span+=ts[-1]-ts[0]
        assert span<=cohort['raw_ns']

def main():
    w=Path(sys.argv[1]).resolve()
    dst=w/'evidence/published/runs';dst.mkdir(exist_ok=True)
    tmp=w/'temp'
    env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(tmp/'gotmp'))
    meta=dict(platform=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
        GOMAXPROCS=8,GOGC=100,binaries={})
    for mode in ('base','on'):
        binary=tmp/mode
        meta['binaries'][mode]=dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),bytes=binary.stat().st_size,
            build=subprocess.check_output(['go','version','-m',binary],text=True))
    (dst/'environment.json').write_text(json.dumps(meta,indent=2)+'\n')
    for block,order in enumerate(('ABC','ABC','BCA','CAB')):
        forks=1 if block==0 else 12
        for sql in order:
            modes=('base','on') if block%2 else ('on','base')
            for mode in modes:
                name=f'{block}-{sql}-{mode}'
                capture=tmp/(name+'.json')
                result=subprocess.run([tmp/mode,'-arm',sql,'-forks',str(forks)],env=dict(env,TIMELINE_OUT=str(capture)),
                                      text=True,capture_output=True)
                if result.returncode:
                    raise RuntimeError(name+' '+result.stderr)
                rows=[json.loads(s) for s in result.stdout.splitlines()]
                assert len(rows[0]['registered'])=={'A':5,'B':5,'C':4}[sql]
                assert [(r['db'],r['inserts'],r['close']) for r in rows[1:]]==[(i,100,'pass') for i in range(forks)]
                if mode=='on':
                    raw=capture.read_bytes()
                    tracecheck(json.loads(raw),rows[1:],sql)
                    (dst/(name+'.json.gz')).write_bytes(gzip.compress(raw,mtime=0))
                (dst/(name+'.jsonl')).write_text(result.stdout)
                print(name,'pass',flush=True)
if __name__=='__main__':main()
