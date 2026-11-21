"""Balanced sequential P1 controls with per-request correctness/ownership checks."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

MODES=('base','outer','phase','detail')
ORDERS=(('base','outer','detail','phase'),('outer','phase','base','detail'),
        ('phase','detail','outer','base'),('detail','base','phase','outer'))
def validate(trace,rows,sql,mode):
    assert len(trace)==len(rows)
    ids=set()
    for db,(items,raw) in enumerate(zip(trace,rows)):
        assert len(items)==100
        total=0
        for j,r in enumerate(items):
            ts=r['T']; ns=r['TriggerNS']
            assert (r['DB'],r['Ordinal'])==(db,j) and (db,r['ID']) not in ids and r['ID']>0
            ids.add((db,r['ID']))
            assert len(ts)==21 and 0<ts[0] and all(a<=b for a,b in zip(ts,ts[1:]))
            assert j==0 or (items[j-1]['T'][-1]<=ts[0] and items[j-1]['ID']<r['ID'])
            assert r['TriggerCalls']==(2 if sql=='C' else 4) and 0<ns<=ts[9]-ts[8]
            total+=ts[-1]-ts[0]
            if mode=='outer':
                assert 'Inner' not in r
                continue
            c=r['Inner'];mat=c['NS'];calls=c['MemCalls']
            assert len(mat)==14 and all(len(row)==6 and min(row)>=0 for row in mat)
            assert sum(map(sum,mat))==ns
            assert list(map(sum,c['SubtreeMem']))==c['SubtreeNS']
            sub,upd,both=c['SubtreeNS']
            assert 0<=both<=min(sub,upd) and sub+upd-both<=ns
            assert all(ref<=v[4] for ref,v in zip(c['ArenaRefills'],calls))
            if mode=='phase':
                assert sum(map(sum,calls))==0 and all(sum(row[1:])==0 for row in mat)
            if sql=='C':
                assert sub==upd==0
            if sql=='A':
                assert sub>0 and upd>0
            if sql!='C':
                assert c['PhaseCalls'][5]>0 and c['PhaseCalls'][6]>0 and c['PhaseCalls'][12]>0
                if mode=='detail': assert sum(v[4] for v in calls)>0
        assert total<=raw['raw_ns']
def main():
    w=Path(sys.argv[1]).resolve(); t=w/'temp'; out=w/'evidence/published/runs';out.mkdir(exist_ok=True)
    env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'))
    meta=dict(host=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
              parallel_databases=1,gomaxprocs=8,gogc=100,binaries={})
    for m in MODES:
        b=t/m
        meta['binaries'][m]=dict(sha256=hashlib.sha256(b.read_bytes()).hexdigest(),bytes=b.stat().st_size,
                                   go=subprocess.check_output(['go','version','-m',b],text=True))
    (out/'environment.json').write_text(json.dumps(meta,indent=2)+'\n')
    for block,seq in enumerate(('ABC','ABC','BCA','CAB','CBA')):
        forks=1 if block==0 else 12
        for sql in seq:
            for mode in (MODES if block==0 else ORDERS[block-1]):
                name=f'{block}-{sql}-{mode}';capture=t/'capture.json'
                result=subprocess.run([t/mode,'-arm',sql,'-forks',str(forks)],capture_output=True,text=True,
                                      env=dict(env,TIMELINE_OUT=str(capture)))
                if result.returncode: raise RuntimeError(name+' '+result.stderr)
                rows=[json.loads(l) for l in result.stdout.splitlines()]
                assert rows[0]['arm']==sql and len(rows[0]['registered'])=={'A':5,'B':5,'C':4}[sql]
                assert [(r['db'],r['inserts'],r['close']) for r in rows[1:]]==[(j,100,'pass') for j in range(forks)]
                if mode!='base':
                    data=capture.read_bytes()
                    validate(json.loads(data),rows[1:],sql,mode)
                    (out/(name+'.json.gz')).write_bytes(gzip.compress(data,compresslevel=1,mtime=0))
                (out/(name+'.jsonl')).write_text(result.stdout)
                print(name,'pass',flush=True)
if __name__=='__main__':main()
