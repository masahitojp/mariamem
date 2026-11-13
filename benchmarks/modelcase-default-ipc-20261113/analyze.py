from pathlib import Path
import json,statistics,collections
r=Path(__file__).resolve().parent;out={}
a=json.loads((r/'comparison-runs.json').read_text());assert len(a)==12
for n in ['pgmem','maria']:
 rows=[x for x in a if x['target']==n and x['repeat']>=0];assert len(rows)==5
 assert all(x['returncode']==0 and x['leaf_pass']==70 for x in a)
 out[n]={'wall_ms':statistics.median(x['wall_ms'] for x in rows)}
 for k in ['elapsed','boot','import','snapshot','fork','sample','test']:
  v=[]
  for x in rows:
   t=json.loads((r/f"comparison-{n}-{x['repeat']}.json").read_text());assert sum(s['name']=='test' for s in t['spans'])==70
   v.append(t['elapsed_ms'] if k=='elapsed' else statistics.median(s['end_ms']-s['start_ms'] for s in t['spans'] if s['name']==k))
  out[n][k]=statistics.median(v)
ipc=[]
for i in range(3):
 ls=[json.loads(p.read_text()) for p in (r/f'ipc-1-{i}-ipc').glob('db-*.json')];assert len(ls)==22
 assert {x['label'] for x in ls} >= {'root','reader'}
 d={}
 for x in ls:
  assert not x['exit_error']
  for a,b in [('host_write','guest_read'),('guest_write','host_read')]:
   assert x['directions'][a]['bytes']==x['directions'][b]['bytes']
   assert x['directions'][a]['frames']==x['directions'][b]['frames']
 for direction in ['host_write','guest_read','guest_write','host_read']:
  ds=[x['directions'][direction] for x in ls];o={k:sum(v[k] for v in ds) for k in ['calls','bytes','frames','zero_frames','call_elapsed_ns']}
  sizes=collections.Counter()
  for v in ds:sizes.update({int(k):z for k,z in v['returned_sizes'].items()})
  o['zero_byte_calls']=sizes[0];o['three_byte_calls']=sizes[3];o['four_byte_calls']=sizes[4];d[direction]=o
 ipc.append(d)
rows=json.loads((r/'ipc-runs.json').read_text());assert len(rows)==11 and all(x['returncode']==0 for x in rows)
obs={str(on):statistics.median(x['wall_ms'] for x in rows if x['name'].startswith('ipc-'+str(on)+'-')) for on in [0,1]}
(r/'summary.json').write_text(json.dumps({'comparison':out,'ipc':ipc,'observer_wall_medians':obs},indent=2));print('PASS: five comparison pairs, 3 IPC pairs, 66 joined DBs, matched bytes/frames')
