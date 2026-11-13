from pathlib import Path
import json,statistics
r=Path(__file__).resolve().parent;rows=json.loads((r/'runs.json').read_text());assert len(rows)==18
assert all(x['returncode']==0 and x['leaf_pass']==70 for x in rows)
out={};counts={}
for arm in ['baseline','candidate']:
 a=[x for x in rows if x['name'].startswith('primary-') and x['arm']==arm];assert len(a)==5
 out[arm]={k:statistics.median(x[k] for x in a) for k in ['wall_ms','cpu_ms','user_ms','system_ms']}
 for x in a:
  t=json.loads((r/(x['name']+'-trace.json')).read_text());assert sum(s['name']=='test' for s in t['spans'])==70
 c=[]
 for i in range(3):
  ds=[json.loads(p.read_text()) for p in (r/f'count-{arm}-{i}-ipc').glob('db-*.json')];assert len(ds)==22 and all(not d['exit_error'] for d in ds)
  for d in ds:
   for a,b in [('host_write','guest_read'),('guest_write','host_read')]:
    assert d['directions'][a]['bytes']==d['directions'][b]['bytes']
    assert d['directions'][a]['frames']==d['directions'][b]['frames']
  v={'writes':sum(d['directions']['guest_write']['calls'] for d in ds),'empty':sum(d['directions']['guest_write']['returned_sizes'].get('0',0) for d in ds),'response_frames':sum(d['directions']['guest_write']['frames'] for d in ds),'bytes':sum(d['directions']['guest_write']['bytes'] for d in ds)}
  assert (v['empty']==0 if arm=='candidate' else v['empty']>5000);c.append(v)
 counts[arm]=c
pairs=[]
for i in range(5):
 a=next(x for x in rows if x['name']==f'primary-baseline-{i}');b=next(x for x in rows if x['name']==f'primary-candidate-{i}')
 pairs.append({k:100*(b[k]/a[k]-1) for k in ['wall_ms','cpu_ms','user_ms','system_ms']})
(r/'summary.json').write_text(json.dumps({'medians':out,'counts':counts,'paired_changes_pct':pairs,'paired_median_pct':{k:statistics.median(p[k] for p in pairs) for k in pairs[0]}},indent=2));print('PASS: 1260 leaf tests, 132 joined DBs, bytes/frames, zero-write suppression and fixed-pair summary')
