"""Negative controls on private copies; leave the published receipt unchanged."""
from pathlib import Path
import tempfile,shutil,json,gzip,subprocess,sys,hashlib
p=Path(__file__).parent
files=['records.json','observations.json.gz','timings.json.gz','owner-summary.json','plan.json','inputs.json','summary.json','stages.json']
def digest():return {n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in files}
before=digest()
def invoke(root,script):return subprocess.run([sys.executable,'-B',str(p/script),str(root),'--check'],capture_output=True,text=True)
assert invoke(p,'analyze.py').returncode==0 and invoke(p,'diagnostic.py').returncode==0
checks=[]
for kind in ['summary','oracle','missing_flag','extra_record','trace_boundary','clock','owner','stage_summary']:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)
  for n in files:shutil.copy(p/n,q/n)
  script='analyze.py'
  if kind=='summary':v=json.loads((q/'summary.json').read_text());v['next_stage_screen_pass']=not v['next_stage_screen_pass'];(q/'summary.json').write_text(json.dumps(v))
  elif kind=='extra_record':v=json.loads((q/'records.json').read_text());v.append(v[0]);(q/'records.json').write_text(json.dumps(v))
  elif kind=='owner':
   script='diagnostic.py';v=json.loads((q/'owner-summary.json').read_text());v[0]['child_indices'].pop();(q/'owner-summary.json').write_text(json.dumps(v))
  elif kind=='stage_summary':
   script='diagnostic.py';v=json.loads((q/'stages.json').read_text());v['scope']='altered';(q/'stages.json').write_text(json.dumps(v))
  else:
   v=json.loads(gzip.decompress((q/'observations.json.gz').read_bytes()));rs=json.loads((q/'records.json').read_text())
   r=next(r for r in rs if r['arm']=='pages' and r['kind']==('diagnostic' if kind in ['trace_boundary','clock'] else 'primary'));o=v[r['report']]
   if kind=='oracle':o['samples'][0]['oracle']=False
   elif kind=='missing_flag':o['image_before_close']['image_ranges']=[x for x in o['image_before_close']['image_ranges'] if not x['offset']<=26981552<x['offset']+x['length']]
   elif kind=='trace_boundary':script='diagnostic.py';o['samples'][0]['traces']['startup']['events']=[x for x in o['samples'][0]['traces']['startup']['events'] if x['name']!='runtime/map_begin']
   elif kind=='clock':script='diagnostic.py';o['samples'][0]['traces']['startup']['epoch_ns']=0
   (q/'observations.json.gz').write_bytes(gzip.compress(json.dumps(v).encode()))
  assert invoke(q,script).returncode!=0,kind
  checks.append(kind)
assert digest()==before
print('PASS: 8 negative controls; published inputs unchanged:',', '.join(checks))
