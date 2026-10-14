import json, os, sys, time
from pathlib import Path
root=Path(__file__).resolve().parents[4]; sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard, run_guarded
w=Path(__file__).resolve().parents[1]; ev=w/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',GOCACHE=str(w/'temp/go-cache'),GOTMPDIR=str(w/'temp/go-tmp'),TMPDIR=str(w/'temp/os-tmp'))
(w/'temp/tools').mkdir(exist_ok=True)
cmd=['go','build','-p','1','-o',str(w/'temp/tools/'),'cmd/pprof','cmd/trace']
g=DiskGuard(w,min_free_gib=8,budget_gib=6); start=time.time()
with (ev/'build-tools.log').open('w') as f: rc=run_guarded(cmd,g,cwd=w/'temp/source',env=env,output=f,interval=5,timeout=600)
(ev/'build-tools.json').write_text(json.dumps({'command':cmd,'returncode':rc,'seconds':time.time()-start,'guard':g.__dict__},default=str,indent=2))
sys.exit(rc)
