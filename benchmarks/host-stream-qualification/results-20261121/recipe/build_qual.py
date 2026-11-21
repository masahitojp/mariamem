from pathlib import Path
import hashlib,json,subprocess,os,sys
w=Path(sys.argv[1]).resolve();t=w/'temp';src=w/'worktree';rec=Path(__file__).resolve().parent
mode=sys.argv[2]
identity=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=src))
assert identity['source_commit']=='5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'
prior='de04aaa7aaf2b8d67c764012111feed6b3d34bac:benchmarks/host-framed-transport/results-20261121/recipe/'
for f in ('overlay.py','pipe.go.txt'):
    assert (rec/f).read_bytes()==subprocess.check_output(['git','show',prior+f],cwd=src)
(t/'gotmp').mkdir(exist_ok=True,parents=True)
env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
subprocess.run([sys.executable,rec/'overlay.py',w,'raw'],check=True)
if mode=='perf':
    subprocess.run([sys.executable,rec/'prepare_perf.py',w],check=True)
    subprocess.run(['go','build','-trimpath','-buildvcs=false','-p','1','-mod=readonly','-overlay',t/'overlay.json','-o',t/'perf','.'],cwd=t/'harness',env=env,check=True)
elif mode=='fault':
    subprocess.run([sys.executable,rec/'prepare_fault.py',w],check=True)
    subprocess.run(['go','test','-c','-trimpath','-vet=off','-p','1','-overlay',t/'fault-overlay.json','-o',t/'fault.test','./internal/host'],cwd=src,env=env,check=True)
else: raise ValueError(mode)
