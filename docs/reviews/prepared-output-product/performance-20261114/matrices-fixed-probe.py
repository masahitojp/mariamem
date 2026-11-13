from pathlib import Path
import subprocess,os,json
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);w=parser.parse_args().workspace.resolve();root=w/'candidate';python=w/'temp/venv/bin/python';env=dict(os.environ,PYTHONPATH=str(root/'python'),PYTHONDONTWRITEBYTECODE='1')
results=[]
for variant in ['fixed']:
 for probe,fixture in [('v06_prepared_p2_probe.py','prepared-p2-native.json'),('v06_prepared_p2_matrix.py','prepared-p2-matrix-native.json'),('v06_prepared_p2_repair_probe.py','prepared-p2-repair-native.json'),('v06_prepared_p3_matrix.py','prepared-p3-native.json')]:
  out=w/'evidence'/(variant+'-'+probe.removesuffix('.py')+'.json')
  command=[str(python),str(root/'tests'/probe),'--host',str(w/'artifacts'/(variant+'-host')),'--reference',str(root/'tests/fixtures'/fixture),'--output',str(out)]
  if 'p3_matrix' in probe:command+=['--require-advertisement']
  with out.with_suffix('.log').open('w') as log:p=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
  results.append(dict(variant=variant,probe=probe,returncode=p.returncode));print(results[-1],flush=True)
(w/'evidence/matrices-fixed-summary.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(int(any(r['returncode'] for r in results)))
