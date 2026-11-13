from pathlib import Path
import subprocess,os,json,hashlib
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
results=[]
for arm in ['0','1']:
 e['MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE']=arm
 p=subprocess.run(['go','test','-v','-overlay',str(r/'evidence/overlay.json'),'-count=1','./internal/generatedgo/code/base','./internal/guest'],cwd=r/'worktree',env=e,capture_output=True,text=True)
 (r/'evidence'/f'unit-{arm}.txt').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True);results.append({'candidate':arm=='1','returncode':p.returncode})
 (r/'evidence/unit-results.json').write_text(json.dumps(results,indent=2))
 if p.returncode:raise SystemExit('focused boundary tests failed')
e['MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE']='0'
subprocess.run(['go','test','-v','-overlay',str(r/'evidence/overlay.json'),'-c','-o',str(r/'temp/maria.test'),'./store'],cwd=r/'temp/maria',env=e,check=True)
(r/'evidence/binary.sha256').write_text(hashlib.sha256((r/'temp/maria.test').read_bytes()).hexdigest()+'\n')
