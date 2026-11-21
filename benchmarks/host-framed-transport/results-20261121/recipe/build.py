"""Recreate the SQL harness from immutable inputs and build one comparison arm."""
import json
import os
from pathlib import Path
import subprocess
import sys

w=Path(sys.argv[1]).resolve()
arm=sys.argv[2]
src=w/'worktree'
t=w/'temp'
h=t/'harness'
rec=Path(__file__).parent.resolve()
fixed='5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'
assert json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=src))['source_commit']==fixed
assert arm in ('raw','trace')
prior='7c5893b3:benchmarks/trigger-sum-bottleneck/results-20261121/recipe/'
for f in ('main.go','restore.py'):
    (t/f).write_bytes(subprocess.check_output(['git','show',prior+f],cwd=src))
subprocess.run([sys.executable,t/'restore.py',h,src],check=True)
s=(h/'main.go').read_text()
def replace(old,new):
    global s
    assert s.count(old)==1,old
    s=s.replace(old,new)
replace('"runtime/pprof"','"runtime/pprof"\n"syscall"')
replace('func run() {','var forks=flag.Int("forks",43,"fixed fresh DBs per process")\nvar rawCPU int64\nfunc processCPU() int64 {var u syscall.Rusage; must(syscall.Getrusage(syscall.RUSAGE_SELF,&u)); return u.Utime.Nano()+u.Stime.Nano()}\nfunc run() {')
replace('start := time.Now()', 'beginCPU:=processCPU()\nstart := time.Now()')
replace('elapsed := time.Since(start)','elapsed := time.Since(start)\nrawCPU=processCPU()-beginCPU')
replace('"raw_ns": elapsed.Nanoseconds()', '"raw_ns": elapsed.Nanoseconds(), "process_cpu_ns":rawCPU')
replace('deadline := time.Now().Add(*duration)','')
replace('time.Now().After(deadline)','i+1>=*forks')
(h/'main.go').write_text(s)
env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOTOOLCHAIN='local',
         GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
(t/'gotmp').mkdir(exist_ok=True)
args=['go','build','-trimpath','-buildvcs=false','-p','1','-mod=readonly']
subprocess.run([sys.executable,rec/'overlay.py',w,arm],check=True)
args+=['-overlay',t/'overlay.json']
subprocess.run(args+['-o',t/arm,'.'],env=env,cwd=h,check=True)
