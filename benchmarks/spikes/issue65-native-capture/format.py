import os,subprocess
from pathlib import Path
w=Path('.').resolve();env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOPATH=str(w/'temp/gopath'),GOMODCACHE=str(w/'temp/modcache'),GOCACHE=str(w/'temp/gocache'));fmt=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())/'bin/gofmt'
for p in (w/'temp/tools').glob('*.go.txt'):
 result=subprocess.run([str(fmt)],input=p.read_text(),capture_output=True,text=True);assert result.returncode==0,(p,result.stderr);p.write_text(result.stdout)
