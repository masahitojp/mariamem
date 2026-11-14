from pathlib import Path
import json,subprocess,shutil
W=Path('build/experiment-work/host-shim-cost');E=W/'evidence';D=E/'campaign188';V=D/'validation';V.mkdir(exist_ok=True)
name='p1-warm-a1';obs=json.loads((D/(name+'-events.json')).read_text());clients=(D/(name+'-clients.json')).read_bytes()
for kind in ['duplicate','missing']:
 data=json.loads(json.dumps(obs));inst=next(x for x in data if x['Label']=='raw/child0');i=next(i for i,e in enumerate(inst['Events'])if e['Name']=='stage3')
 if kind=='duplicate':inst['Events'].append(inst['Events'][i])
 else:inst['Events'].pop(i)
 (V/(kind+'-events.json')).write_text(json.dumps(data));(V/(kind+'-clients.json')).write_bytes(clients)
 with(V/(kind+'.txt')).open('w')as f:r=subprocess.run(['python3',str(E/'reduce188.py'),str(V),kind],stdout=f,stderr=f)
 assert r.returncode!=0
print('missing/duplicate rejection PASS')
