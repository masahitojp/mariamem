from pathlib import Path
import shutil,json,subprocess
r=Path(__file__).resolve().parents[1];e=r/'evidence';out=[]
for name in ['nonzero_empty_writes','missing_joined_db','wrong_bytes']:
 d=r/'temp/controls'/name;d.mkdir(parents=True,exist_ok=True)
 for p in e.glob('*-trace.json'):shutil.copy2(p,d/p.name)
 for n in ['runs.json','analyze.py']:shutil.copy2(e/n,d/n)
 for arm in ['baseline','candidate']:
  for i in range(3):shutil.copytree(e/f'count-{arm}-{i}-ipc',d/f'count-{arm}-{i}-ipc',dirs_exist_ok=True)
 p=next((d/'count-candidate-0-ipc').glob('db-*.json'))
 if name=='missing_joined_db':p.unlink()
 else:
  x=json.loads(p.read_text())
  if name=='wrong_bytes':x['directions']['host_write']['bytes']+=1
  else:x['directions']['guest_write']['returned_sizes']['0']=1
  p.write_text(json.dumps(x))
 result=subprocess.run(['python3',str(d/'analyze.py')],capture_output=True,text=True);assert result.returncode!=0,name
 out.append({'control':name,'rejected':True})
(e/'negative-controls.json').write_text(json.dumps(out,indent=2));print('PASS: 3 corrupted evidence controls rejected')
