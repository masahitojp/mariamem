"""Independent consistency and rejection checks on the saved campaign."""
import copy
import gzip
import json
from pathlib import Path
import sys
from campaign import tracecheck

out=Path(sys.argv[1])/'runs'
total=timed=main=0
for p in sorted(out.glob('*.jsonl')):
    block,sql,mode=p.stem.split('-')
    lines=[json.loads(s) for s in p.read_text().splitlines()]
    raw=lines[1:]
    assert len(raw)==(1 if block=='0' else 12)
    assert all(o['inserts']==100 and o['close']=='pass' for o in raw)
    total+=100*len(raw)
    if mode=='on':
        data=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
        tracecheck(data,raw,sql)
        timed+=100*len(raw)
        if block!='0':main+=100*(len(raw)-2)
assert (total,timed,main)==(22200,11100,9000)
data=json.loads(gzip.decompress((out/'0-A-on.json.gz').read_bytes()))
raw=[json.loads(s) for s in (out/'0-A-on.jsonl').read_text().splitlines()][1:]
def reject(change):
    bad=copy.deepcopy(data)
    change(bad)
    try:tracecheck(bad,raw,'A')
    except AssertionError:return
    raise AssertionError('damaged trace accepted')
reject(lambda b:b[0].pop())
reject(lambda b:b[0][1].update(ID=b[0][0]['ID']))
reject(lambda b:b[0][1]['T'].__setitem__(13,b[0][1]['T'][12]-1))
reject(lambda b:b[0][1].update(TriggerNS=b[0][1]['T'][9]-b[0][1]['T'][8]+1))
print('All 24 processes, 222 DBs, 22200 INSERTs passed; 11100 timed, 9000 retained for stage averages. Four damaged traces rejected.')
