"""Pair the optimizer-only binary with four selected call sites in alternating order."""
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
from statistics import mean
import subprocess
import sys
from campaign import validate

def run(w):
    dst=w/'evidence/published/focus'
    dst.mkdir(exist_ok=True)
    temp=w/'temp'
    env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(temp/'gotmp'))
    info={}
    for mode in ('parent','focus'):
        exe=temp/mode
        info[mode]=dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                        go=subprocess.check_output(['go','version','-m',exe],text=True))
    (dst/'binaries.json').write_text(json.dumps(info,indent=2)+'\n')
    jobs=[(0,s,'focus') for s in 'ABC']
    for b in range(1,5):
        jobs.extend((b,'A',m) for m in (('parent','focus') if b%2 else ('focus','parent')))
    for b,sql,mode in jobs:
        name=f'{b}-{sql}-{mode}';capture=temp/'focus-capture.json'
        forks=12 if b else 1
        cmd=[temp/mode,'-arm',sql,'-forks',str(forks)]
        out=subprocess.run(cmd,capture_output=True,text=True,env=dict(env,TIMELINE_OUT=str(capture)),check=True)
        observations=[json.loads(s) for s in out.stdout.splitlines()]
        rows=observations[1:]
        assert len(rows)==forks
        trace=capture.read_bytes()
        validate(json.loads(trace),rows,sql,mode)
        (dst/(name+'.jsonl')).write_text(out.stdout)
        (dst/(name+'.json.gz')).write_bytes(gzip.compress(trace,compresslevel=1,mtime=0))
        print(name,'pass',flush=True)

def reduce(dst):
    folder=dst/'focus'
    edges=json.loads((dst/'edges.json').read_bytes())['edges']
    targets={'15009':'statistics','15010':'stage2','12791':'quick_select','12795':'key_scans'}
    chosen={str(e['id']):targets[e['target']] for e in edges if
            (e['caller'],e['target']) in {('15000','15009'),('15000','15010'),('15009','12791'),('12791','12795')}}
    assert len(chosen)==4
    rows=[]; processes=dbs=0
    common=json.loads((dst/'runs/environment.json').read_bytes())['binaries']['parent']['sha256']
    assert json.loads((folder/'binaries.json').read_bytes())['parent']['sha256']==common
    for fn in sorted(folder.glob('*.jsonl')):
        b,s,m=fn.stem.split('-')
        observations=[json.loads(l) for l in fn.read_text().splitlines()]
        meta=observations[0];groups=observations[1:]
        assert meta['arm']==s and len(meta['registered'])==(4 if s=='C' else 5)
        assert all(x['db']==i and x['inserts']==100 and x['close']=='pass' for i,x in enumerate(groups))
        data=json.loads(gzip.decompress(fn.with_suffix('.json.gz').read_bytes()))
        validate(data,groups,s,m)
        for batch in data:
            for r in batch:
                if s=='A':
                    assert set(r['Join'])==({'0'} if m=='parent' else {'0',*chosen})
        dbs+=len(data);processes+=1
        if b=='0':continue
        n=len(data)-2
        batch=[r['Join'] for g in data[2:] for r in g]
        v=dict(block=int(b),mode=m,raw_ms100=mean(r['raw_ns'] for r in groups[2:])/1e6,
               parent_ms100=sum(r['0']['Inclusive'] for r in batch)/n/1e6)
        for k,name in chosen.items():
            for field in ('Calls','Inclusive','Exclusive'):
                v[name+'_'+field]=sum(r[k][field] for r in batch)/n/(1 if field=='Calls' else 1e6) if m=='focus' else ''
        rows.append(v)
    assert (processes,dbs)==(11,99) and len(rows)==8
    with (dst/'focus.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    (dst/'focus-verification.json').write_text(json.dumps(dict(processes=processes,databases=dbs,inserts=dbs*100,steady_inserts=8000),indent=2)+'\n')
if __name__=='__main__':
    w=Path(sys.argv[2]).resolve()
    if sys.argv[1]=='run': run(w)
    elif sys.argv[1]=='reduce': reduce(w)
    else: raise ValueError(sys.argv[1])
