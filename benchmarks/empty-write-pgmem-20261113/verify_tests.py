from pathlib import Path
import subprocess,os,json
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
for arm in ['0','1']:
 e['MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE']=arm
 p=subprocess.run(['go','test','-v','-overlay',str(r/'evidence/overlay.json'),'-count=1','-run','TestExperiment|TestFDWrite','./internal/generatedgo/code/base'],cwd=r/'worktree',env=e,capture_output=True,text=True)
 (r/'evidence'/f'focused-details-{arm}.txt').write_text(p.stdout+p.stderr)
 assert p.returncode==0 and 'TestExperimentFDWriteEmptyVectorValidation' in p.stdout
 print(arm,'focused named tests PASS')
