"""Run the installed generator's own static-image finalization step."""
import hashlib,json,os,subprocess,sys
from pathlib import Path

w=Path(sys.argv[1]).resolve()
src=w/'worktree'
sys.path.insert(0,str(src/'scripts'))
from runtime_static_image import generate
target=src/'internal/generatedgo'
os.environ.update(TMPDIR=str(w/'temp/gotmp'),GOCACHE=str(w/'temp/gocache'),GOPROXY='off',GOMAXPROCS='6')
import tempfile
tempfile.tempdir=str(w/'temp/gotmp')
goroot=Path(subprocess.check_output(['go','env','GOROOT'],env=dict(os.environ,GOTOOLCHAIN='go1.26.11'),text=True).strip())
generate(target,goroot/'bin/go')
p=target/'provenance.json'
d=json.loads(p.read_bytes())
d['files_sha256']['image/layout.json']=hashlib.sha256((target/'image/layout.json').read_bytes()).hexdigest()
p.write_text(json.dumps(d,indent=2)+'\n')
