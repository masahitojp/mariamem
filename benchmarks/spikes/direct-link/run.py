#!/usr/bin/env python3
"""Bounded functional and fault-containment probes, not a product benchmark."""
import argparse,json,subprocess,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();exe=(a.work/'probe').resolve();rows=[]
for n in range(3):
 r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=50)
 if r.returncode:raise RuntimeError(r.stderr)
 v=json.loads(r.stdout)
 assert len(v['results'])==3 and v['goroutines_before']==v['goroutines_after'],v
 assert all(x['shutdown'] for x in v['results']),v
 rows.append(v)
faults=[]
for mode,code,marker in [('worker-panic',2,'injected worker failure'),('entry-failure',1,'generated-Go failure')]:
 r=subprocess.run([str(exe),mode],capture_output=True,text=True,timeout=15)
 assert r.returncode==code and marker in r.stderr,(mode,r.returncode,r.stderr)
 faults.append({'mode':mode,'exit_code':r.returncode,'stderr':r.stderr[:2200]})
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'adapter_inputs':json.loads((a.work/'inputs.json').read_text()),'probe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'normal':rows,'faults':faults},indent=2)+'\n')
print(json.dumps({'normal_runs':len(rows),'faults':[(r['mode'],r['exit_code']) for r in faults]}))
