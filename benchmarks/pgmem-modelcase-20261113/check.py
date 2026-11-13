import json,hashlib,statistics
from pathlib import Path
r=Path(__file__).resolve().parent
for name,digest in json.loads((r/'SHA256SUMS.json').read_text()).items():
 assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest,name
rows=json.loads((r/'runs.json').read_text());assert len(rows)==12
for target in ['maria','pgmem']:
 rr=[x for x in rows if x['target']==target];assert len(rr)==6
 for x in rr:
  assert x['returncode']==0 and x['leaf_pass']==70
  t=json.loads((r/f"{target}-{x['repeat']}.json").read_text());assert sum(s['name']=='test' for s in t['spans'])==70
  assert sum(s['name']=='fork' for s in t['spans'])==20
 expected=json.loads((r/'summary.json').read_text())[target]['wall_ms']
 assert statistics.median(x['wall_ms'] for x in rr if x['repeat']>=0)==expected
print('PASS: checksums, 840 leaves, 12 traces, fixed five-pair summary')
