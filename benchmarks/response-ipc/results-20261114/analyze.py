from pathlib import Path
import json,collections
E=Path(__file__).resolve().parent;summary=[]
for i in range(3):
 files=list((E/f'r{i}-on').glob('*.json'));assert len(files)==22,len(files)
 counts={k:collections.Counter()for k in ['guest_read','guest_write','host_read','host_write']};sizes={k:collections.Counter()for k in counts};opcodes=collections.Counter()
 for f in files:
  d=json.loads(f.read_text());assert not d['exit_error'];ds=d['directions']
  for a,b in [('guest_write','host_read'),('host_write','guest_read')]:
   assert ds[a]['bytes']==ds[b]['bytes'],(f,a,b)
   assert ds[a]['frames']==ds[b]['frames'],(f,a,b)
  for k in counts:
   for n in ['calls','bytes','frames','zero_frames']:counts[k][n]+=ds[k][n]
   sizes[k].update(ds[k]['returned_sizes'])
  opcodes.update(ds['host_write'].get('opcodes',{}))
 trace=json.loads((E/f'r{i}-on.json').read_text());assert len([s for s in trace['spans']if s['kind']in ['read','write']])==70
 summary.append({'round':i,'dbs':len(files),'counts':counts,'sizes':sizes,'opcodes':opcodes})
(E/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
