import json, os, subprocess, sys, time, hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard, run_guarded
from git_identity import require_commit, verify_go_binary
w=Path(__file__).resolve().parents[1]; src=w/'temp/source'; ev=w/'evidence'
env=os.environ.copy()
for k in ('GOGC','GOMEMLIMIT','GODEBUG','GOFLAGS','MARIAMEM_TIMING_DIR'): env.pop(k,None)
env.update(GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',CGO_ENABLED='1',GOCACHE=str(w/'temp/go-cache'),GOTMPDIR=str(w/'temp/go-tmp'),TMPDIR=str(w/'temp/os-tmp'))
for p in ('go-cache','go-tmp','os-tmp'): (w/'temp'/p).mkdir(exist_ok=True)
guard=DiskGuard(w,min_free_gib=8,budget_gib=6)
rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip()
require_commit(src,rev)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=src,text=True)
command=['go','build','-p','1','-buildvcs=true','-o',str(w/'temp/ownedprepared'),'./benchmarks/ownedprepared']
started=time.time()
with (ev/'build.log').open('w') as log:
    rc=run_guarded(command,guard,cwd=src,env=env,output=log,interval=5,timeout=1800)
(ev/'build.json').write_text(json.dumps({'source_commit':rev,'command':command,'returncode':rc,'seconds':time.time()-started,'guard':guard.__dict__},default=str,indent=2))
if rc: sys.exit(rc)
info=verify_go_binary(src,w/'temp/ownedprepared',rev)
(ev/'binary-buildinfo.txt').write_text(info)
(ev/'inputs.json').write_text(json.dumps({'source_commit':rev,'binary_sha256':hashlib.sha256((w/'temp/ownedprepared').read_bytes()).hexdigest(),'env':{k:env.get(k) for k in ['GOTOOLCHAIN','GOMAXPROCS','CGO_ENABLED','GOGC','GOMEMLIMIT','GODEBUG','GOFLAGS']},'platform':subprocess.check_output(['uname','-a'],text=True)},indent=2))
print(json.dumps({'built_source_commit':rev,'seconds':time.time()-started}),flush=True)
