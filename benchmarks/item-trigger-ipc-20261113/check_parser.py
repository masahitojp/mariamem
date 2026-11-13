from pathlib import Path
import os,subprocess
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
p=subprocess.run(['go','test','-v','-overlay',str(r/'evidence/overlay.json'),'-count=1','-run','TestExperimentFrame','./internal/guest'],cwd=r/'worktree',env=e,capture_output=True,text=True);(r/'evidence/parser-tests.txt').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr);assert p.returncode==0
