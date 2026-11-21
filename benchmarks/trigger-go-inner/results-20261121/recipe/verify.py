"""Re-read every result and ensure misattribution or absent measurements fail."""
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
import sys

from campaign import validate,MODES
out=Path(sys.argv[1]);runs=out/'runs'
totals=Counter(); hashes=json.loads((runs/'environment.json').read_bytes())['binaries']
assert set(hashes)==set(MODES) and len({v['sha256'] for v in hashes.values()})==4
for path in sorted(runs.glob('*.jsonl')):
    b,s,m=path.stem.split('-')
    observations=[json.loads(l) for l in path.read_text().splitlines()]
    rows=observations[1:]
    assert all(r['db']==i and r['close']=='pass' and r['inserts']==100 for i,r in enumerate(rows))
    totals['processes']+=1;totals['DBs']+=len(rows)
    totals['inserts']+=100*len(rows)
    if b!='0':totals['steady_inserts']+=100*(len(rows)-2)
    if m!='base':
        data=json.loads(gzip.decompress(path.with_suffix('.json.gz').read_bytes()))
        validate(data,rows,s,m)
        totals['timed_inserts']+=100*len(rows)
    if m in ('phase','detail') and b!='0':
        totals['steady_inner']+=100*(len(rows)-2)
assert totals==dict(processes=60,DBs=588,inserts=58800,steady_inserts=48000,timed_inserts=44100,steady_inner=24000)
path=runs/'0-A-detail.jsonl'
rows=[json.loads(l) for l in path.read_text().splitlines()[1:]]
trace=json.loads(gzip.decompress(path.with_suffix('.json.gz').read_bytes()))
def rejects(fn):
    damaged=copy.deepcopy(trace)
    fn(damaged[0])
    try: validate(damaged,rows,'A','detail')
    except AssertionError: return
    raise AssertionError('damaged trace accepted')
rejects(lambda b:b.pop())
rejects(lambda b:b[1].update(ID=b[0]['ID']))
rejects(lambda b:b[0]['Inner']['NS'][0].__setitem__(0,b[0]['Inner']['NS'][0][0]+1))
rejects(lambda b:b[0]['Inner']['SubtreeNS'].__setitem__(2,b[0]['TriggerNS']+1))
rejects(lambda b:b[0]['Inner']['ArenaRefills'].__setitem__(6,b[0]['Inner']['MemCalls'][6][4]+1))
print(json.dumps(dict(totals=totals,rejected_corrupt_traces=5,verified_modes=MODES),indent=2))
