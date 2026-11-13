from pathlib import Path
import shutil,json,subprocess
r=Path(__file__).resolve().parents[1];e=r/'evidence';out=[]
for kind in ['wrong_bytes','missing_db','exit_error']:
 d=r/'temp/controls'/kind;d.mkdir(parents=True,exist_ok=True)
 for p in e.glob('comparison-*.json'):shutil.copy2(p,d/p.name)
 shutil.copy2(e/'comparison-runs.json',d/'comparison-runs.json');shutil.copy2(e/'ipc-runs.json',d/'ipc-runs.json');shutil.copy2(e/'analyze.py',d/'analyze.py')
 for i in range(3):shutil.copytree(e/f'ipc-1-{i}-ipc',d/f'ipc-1-{i}-ipc',dirs_exist_ok=True)
 p=next((d/'ipc-1-0-ipc').glob('db-*.json'))
 if kind=='missing_db':p.unlink()
 else:
  x=json.loads(p.read_text())
  if kind=='wrong_bytes':x['directions']['host_write']['bytes']+=1
  else:x['exit_error']='injected worker failure'
  p.write_text(json.dumps(x))
 result=subprocess.run(['python3',str(d/'analyze.py')],capture_output=True,text=True)
 assert result.returncode!=0,kind
 out.append({'control':kind,'rejected':True})
(e/'negative-controls.json').write_text(json.dumps(out,indent=2));print('PASS: all three corrupted evidence controls rejected')
