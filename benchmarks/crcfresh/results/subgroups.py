from pathlib import Path
import json,sys,statistics
from stage_core import stats
p=Path(__file__).parent;s=json.loads((p/'summary.json').read_text());owners={x['name']:x for x in json.loads((p/'owner-summary.json').read_text())};out=[]
for proc in s['processes']:
 if proc['kind'] not in ['primary','positive']:continue
 rows=[x for x in s['children'] if x['run']==proc['name']];cs={x['child']:x for x in owners[proc['name']]['crc_children']};keys=['start_or_fork','fork_cpu','seed','close','count_sum']
 groups={}
 for name,pred in [('zero_crc',lambda x:cs[x['child']]['crc_calls']==0),('some_crc',lambda x:cs[x['child']]['crc_calls']>0),('first8',lambda x:x['child']<8),('remaining40',lambda x:x['child']>=8)]:
  rr=[x for x in rows if pred(x)];groups[name]={'n':len(rr),'metrics':{k:stats([x['ms'][k] for x in rr]) for k in keys if rr and all(k in x['ms'] for x in rr)}}
 counts=[x['crc_calls'] for x in cs.values()]
 out.append(dict(name=proc['name'],mode=proc['mode'],arm=proc['arm'],kind=proc['kind'],crc_histogram={str(n):counts.count(n) for n in sorted(set(counts))},groups=groups))
result={'scope':'Post-hoc descriptive subgroups; lifecycle CRC count is not a randomized treatment. Not a new acceptance gate or a causal comparison. Original samples all retained.','processes':out}
if '--check' in sys.argv:assert result==json.loads((p/'subgroups.json').read_text());print('PASS subgroup replay')
else:(p/'subgroups.json').write_text(json.dumps(result,indent=2)+'\n')
