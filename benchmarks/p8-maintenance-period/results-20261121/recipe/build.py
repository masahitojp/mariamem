"""Restore the same modelcase and build raw or diagnostic pairs from checked sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

w = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
t, src, out = w/'temp', w/'worktree', w/'evidence/timer'
rec = out/'recipe'
base = 'be12aeb6ebed61f291d98ffa08b872a03695900b'
candidate = 'a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=src)
for ref, sha in [('HEAD',candidate),(base,base)]:
    ident=json.loads(subprocess.check_output([sys.executable,src/'scripts/git_identity.py','--root',src,'inspect',ref]))
    assert ident['source_commit']==sha
assert not git('status','--porcelain')
h=t/mode
h.mkdir(exist_ok=True)
sha='10665616ba6f00d72b5563158a50bfb7cb2305d2'
prefix='benchmarks/read-transport/harness/'
for name in git('ls-tree','-r','--name-only',sha,prefix).decode().splitlines():
    if name.endswith('/read_profile_test.go'): continue
    dest=h/name[len(prefix):]
    dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_bytes(git('show',sha+':'+name))
p=h/'go.mod'
p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(src)).replace('v1.9.3','v1.10.1').replace('v1.1.0','v1.2.0'))
(h/'go.sum').write_bytes((src/'go.sum').read_bytes())
linked=src/'internal/guest/linked.go'
os_link=t/'baseline-linked.go'
os_link.write_bytes(git('show',base+':internal/guest/linked.go'))
env=dict(os.environ,GOCACHE=str(t/'gocache'),TMPDIR=str(t/'gotmp'),GOMAXPROCS='8',GOTOOLCHAIN='local',GOPROXY='off',GOWORK='off',GOFLAGS='')
for arm in ('ring',):
    mp={str(linked):str(os_link)} if arm=='os' else {}
    if mode=='diag':
        import overlay
        mp=overlay.prepare(w,h,mp,arm)
    import period_overlay
    mp=period_overlay.prepare(w,h,mp,mode)
    path=t/(mode+'-'+arm+'.overlay.json')
    path.write_text(json.dumps({'Replace':mp}))
    args=['go','test','-c','-p','1','-vet=off','-trimpath','-buildvcs=false','-mod=readonly']
    if mp: args+=['-overlay',path]
    exe=t/(mode+'-'+arm+'.test')
    subprocess.run(args+['-o',exe,'./store'],cwd=h,env=env,check=True)
    (out/(mode+'-'+arm+'-build.json')).write_text(json.dumps(dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),go=subprocess.check_output(['go','version','-m',exe],text=True)),indent=2)+'\n')
