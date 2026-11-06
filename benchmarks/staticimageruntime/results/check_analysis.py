"""Replay analysis and negative controls without changing retained evidence."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,shutil
root=Path(__file__).resolve().parent
files=lambda:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
before=files()
subprocess.run([sys.executable,'-B',str(root/'analyze.py'),str(root),'--check'],check=True)
with tempfile.TemporaryDirectory() as directory:
 t=Path(directory)
 for n in ['records.json','observations.json','summary.json','plan.json','inputs.json']:shutil.copyfile(root/n,t/n)
 def rejects():
  r=subprocess.run([sys.executable,'-B',str(root/'analyze.py'),str(t),'--check'],capture_output=True,text=True)
  assert r.returncode!=0 and 'summary differs' in r.stderr,r.stderr
 s=json.loads((t/'summary.json').read_text());s['next_stage_screen_pass']=True;(t/'summary.json').write_text(json.dumps(s));rejects()
 shutil.copyfile(root/'summary.json',t/'summary.json')
 o=json.loads((t/'observations.json').read_text())
 for c in o['anonymous-p1-r0-primary.json']['samples']:
  for v in c['spans']:
   if v['name']=='start_or_fork':v['end_ms']+=1
 (t/'observations.json').write_text(json.dumps(o));rejects()
assert files()==before
print('PASS: negative controls and unchanged evidence')
