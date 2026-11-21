"""Build the plain candidate or add identical measurement points to each arm."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

w = Path(sys.argv[1]).resolve()
arm = sys.argv[2]
assert arm in ('plain','current','split')
src, tmp, out = w/'worktree', w/'temp', w/'evidence/study'
rec = out/'recipe'
base = 'a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
candidate = 'fa7d878d0bdc8616726db0e8a822285f987a2e91'
fixture = '10665616ba6f00d72b5563158a50bfb7cb2305d2'
def git(*args):
    return subprocess.check_output(['git',*args], cwd=src)
for ref, sha in [('HEAD',candidate),(base,base),(fixture,fixture)]:
    identity = json.loads(subprocess.check_output([sys.executable,src/'scripts/git_identity.py','--root',src,'inspect',ref]))
    assert identity['source_commit']==sha
assert not git('status','--porcelain')
h = tmp/arm
prefix = 'benchmarks/read-transport/harness/'
for name in git('ls-tree','-r','--name-only',fixture,prefix).decode().splitlines():
    if name.endswith('/read_profile_test.go'):
        continue
    dest = h/name[len(prefix):]
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(git('show',fixture+':'+name))
module = src
if arm == 'current':
    # Embed metadata and host files from the original checkout as well as the
    # generated functions. Use an independent base module for the control.
    module = tmp/'base-module'
    module.mkdir(exist_ok=True)
    root_go = [name for name in git('ls-tree','--name-only',base).decode().splitlines() if name.endswith('.go')]
    archive = subprocess.Popen(['git','archive',base,'go.mod','go.sum','internal',*root_go],
                               cwd=src,stdout=subprocess.PIPE)
    subprocess.run(['tar','-x','-C',module],stdin=archive.stdout,check=True)
    archive.stdout.close()
    assert archive.wait()==0
mod = h/'go.mod'
mod.write_text(mod.read_text().replace('<MARIAMEM_SOURCE>',str(module)).replace('v1.9.3','v1.10.1').replace('v1.1.0','v1.2.0'))
(h/'go.sum').write_bytes((src/'go.sum').read_bytes())
args = ['go','test','-c','-p','1','-vet=off','-trimpath','-buildvcs=false','-mod=readonly']
if arm != 'plain':
    import measure
    args += ['-overlay', measure.prepare(src,module,tmp,rec,h,arm,base if arm=='current' else candidate)]
env=dict(os.environ,GOCACHE=str(tmp/'gocache'), TMPDIR=str(tmp/'gotmp'),GOMAXPROCS='8',
         GOTOOLCHAIN='local',GOPROXY='off',GOWORK='off',GOFLAGS='')
exe = tmp/(arm+'.test')
subprocess.run(args+['-o',exe,'./store'],cwd=h,env=env,check=True)
(out/(arm+'-build.json')).write_text(json.dumps(dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    source_commit=base if arm=='current' else candidate, fixture=fixture,
    go=subprocess.check_output(['go','version','-m',exe],text=True)),indent=2)+'\n')
