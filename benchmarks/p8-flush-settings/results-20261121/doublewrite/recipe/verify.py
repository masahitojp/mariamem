"""Check saved summary against each process's raw observation and actual settings."""
import csv
import gzip
import itertools
import json
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

out=Path(sys.argv[1])
def rows(name):
    with (out/name).open() as f:return list(csv.DictReader(f))
arms=[r['setting'] for r in rows('summary.csv')]
totals=Counter()
observed=set()
identities=set()
for path in sorted((out/'runs').glob('*.json.gz')):
    r=json.loads(gzip.decompress(path.read_bytes()))
    kind,arm,block,pos=r['kind'],r['arm'],r['block'],r['position']
    assert (kind,block,arm) not in identities
    identities.add((kind,block,arm))
    if kind=='main':
        orders=list(itertools.permutations([a for a in ('default','off') if a in arms]))
        assert 1<=block<=96 and orders[(block-1)%len(orders)][pos]==arm
    assert len(r['windows'])==21 and r['windows'].keys()==r['settings'].keys()
    assert r['counts']['write']==20 and r['counts']['read']==50
    for lane,win in r['windows'].items():
        cfg=r['settings'][lane];before=cfg['before'];after=cfg['after']
        assert len(before)==len(after)==7
        changed=[i for i in range(7) if before[i]!=after[i]]
        assert changed=={'default':[],'off':[4]}[arm]
        assert before[4]=='ON' and after[4]==('OFF' if arm=='off' else 'ON')
        if kind=='main':
            totals[arm,'loads']+=1
            tail=win['end']-win['start']>=400_000_000
            if tail:observed.add((arm,block,lane))
for s in rows('summary.csv'):
    arm=s['setting']
    assert all((kind,block,arm) in identities for kind,block in [('warm',0)]+[('main',b) for b in range(1,97)])
    assert int(s['loads'])==totals[arm,'loads']==2016
    subset={k for k in observed if k[0]==arm}
    assert int(s['tail_loads'])==len(subset)
    assert int(s['tail_suites'])==len({k[1] for k in subset})
all_samples=rows('samples.csv')
assert len(all_samples)==len(arms)*2016
assert {(r['setting'],int(r['block']),r['lane']) for r in all_samples if r['tail']=='True'}==observed
for d in json.loads((out/'details.json').read_text()):
    s,e=d['summary'],d['event']
    assert (s['setting'],s['block'],s['lane']) in observed
    if s['matched_page']:
        a=e['Waker']; t=a['Current'];f=t['Flush']
        assert t['Unique'] and t['ParentUnique'] and f['Page']==a['CallbackPage'] and f['Generation']>0
        assert f['Control']==a['WriteArg']==t['Arg'] and e['Branch']=='notify'
        assert any('write_io_callback(' in fr for fr in d['wake_stack'])
print(f'PASS: {len(arms)} settings, {96*len(arms)} measured processes, {len(all_samples)} loads, {len(observed)} threshold crossings; SQL readback, case counts, block order and matched callback identity verified.')
