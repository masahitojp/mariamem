"""Verify archived cohorts and exact reproduction of table totals after packaging."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

bundle=Path(sys.argv[1])
def data(rel):
    p=bundle/rel
    return p.read_bytes() if p.is_file() else gzip.decompress(Path(str(p)+'.gz').read_bytes())
def lines(rel): return [json.loads(line) for line in data(rel).splitlines()]
def read(rel): return json.loads(data(rel))

phase=read('phase1.json')
table=gzip.decompress(data('functions.txt.gz'))
assert hashlib.sha256(table).hexdigest()==phase['symbol_map_sha256'] and len(table.splitlines())==21791
orders=['validate-A','validate-B','validate-C','1-A','1-B','1-C','2-B','2-C','2-A','3-C','3-A','3-B']
for group in ('cpu','events'):
    runs=lines(group+'/runs.jsonl')
    assert [r['name'] for r in runs]==orders and all(r['rc']==0 for r in runs)
    bodies={}
    for run in runs:
        name,arm=run['name'],run['arm']
        observations=lines(group+'/'+name+'.jsonl')
        registered=observations.pop(0)['registered']
        assert registered==bodies.setdefault(arm,registered)
        assert [r['db'] for r in observations]==list(range(len(observations))) and observations
        assert all(r['inserts']==100 and r['raw_ns']>0 and r['close']=='pass' for r in observations)
        if group=='events':
            observed=read(group+'/'+name+'-events.json')
            assert len(observed['Requests'])==100*len(observations)
            assert all(r['SQLCalls']==1 and r['Depth']==0 for r in observed['Requests'])
        elif not name.startswith('validate'):
            assert gzip.decompress(data(group+'/'+name+'.pprof'))
    assert len(bodies['C'])==4
    for arm in 'AB':
        assert {k:v for k,v in bodies[arm].items() if k!='order_items_total_insert'}==bodies['C']
    assert bodies['A']['order_items_total_insert']!=bodies['B']['order_items_total_insert']
cohorts=list(csv.DictReader((bundle/'pairs.csv').open()))
assert len(cohorts)==9
t1=list(csv.DictReader((bundle/'T1.csv').open()))
for row in cohorts:
    seq,arm=row['triplet'],row['arm']
    for scope in ('sql','trigger'):
        total=sum(float(r[arm+'_ms_per_100']) for r in t1 if r['triplet']==seq and r['scope']==scope)
        assert abs(total-float(row[scope+'_cpu_ms_per_100']))<0.00001
print('Verified 9 CPU profiles, 9 counter replays, 6 preflights, function map and per-process SQL/trigger CPU conservation.')
