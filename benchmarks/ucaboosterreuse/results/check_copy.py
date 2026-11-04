"""Read-only reduction of the supplementary MemoryInit component records."""
from pathlib import Path
import json,statistics,sys,copy
p=Path(sys.argv[1]);data=json.loads((p/'copy-results.json').read_text())
def reduce(d):
 assert d['result']=='PASS' and d['go']=='go1.26.10' and len(d['rows'])==24
 assert sum(bool(x['warmup']) for x in d['rows'])==4
 result={}
 for mode in ['fresh','pretouched']:
  result[mode]={}
  for label,nbytes in [('baseline',6856219),('candidate',9610331)]:
   rows=[x for x in d['rows'] if x['mode']==mode and x['label']==label];assert len(rows)==6 and sum(x['warmup'] for x in rows)==1
   for row in rows:assert row['oracle'] and row['copied_bytes']==nbytes and row['wall_ns']>0 and row['cpu_ns']>0 and row['minor_fault_delta']>=0
   timed=[x for x in rows if not x['warmup']];result[mode][label]={k:statistics.median(x[k] for x in timed) for k in ['wall_ns','cpu_ns','minor_fault_delta','copied_bytes']}
 return result
assert reduce(data)==json.loads((p/'copy-summary.json').read_text())
bad=copy.deepcopy(data);bad['rows'][0]['copied_bytes']-=1
try:reduce(bad)
except AssertionError:pass
else:raise AssertionError('wrong input length admitted')
print('PASS readonly MemoryInit component summary, byte/mapping-mode oracles, corruption rejection')
