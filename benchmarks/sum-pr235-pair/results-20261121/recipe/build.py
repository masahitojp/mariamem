"""Prepare exact-source binaries for the original prepared SUM workload."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
w=Path.cwd();tmp=w/'temp';src=w/'worktree';out=w/'evidence'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=src)
base='be12aeb6ebed61f291d98ffa08b872a03695900b'
ring='a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
recipe='7c5893b3d5198d2c5087dbb100e631dfe63a58bb'
fixture='706072d8dbfa76acb23d302d6bfaa08b91c444b5'
for ref,want in [('HEAD',ring),('HEAD^',base),(recipe,recipe),(fixture,fixture)]:
    d=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect',ref],cwd=src))
    assert d['source_commit']==want and d['object_type']=='commit'
assert not git('status','--porcelain')
for f in ('restore.py','main.go'):
    (tmp/f).write_bytes(git('show',recipe+':benchmarks/trigger-sum-bottleneck/results-20261121/recipe/'+f))
env=dict(os.environ,CGO_ENABLED='0',GOCACHE=str(tmp/'cache'),GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(tmp/'gotmp'),GOMAXPROCS='8')
meta={}
for arm,ref in [('os',base),('ring',ring)]:
    mod=src
    if arm=='os':
        mod=tmp/'parent';mod.mkdir()
        proc=subprocess.Popen(['git','archive',ref],cwd=src,stdout=subprocess.PIPE)
        subprocess.run(['tar','-x','-C',mod],stdin=proc.stdout,check=True);proc.stdout.close();assert proc.wait()==0
    h=tmp/('fixture-'+arm)
    subprocess.run([sys.executable,tmp/'restore.py',h,src],check=True)
    p=h/'go.mod'
    p.write_text(p.read_text().replace(str(src),str(mod)).replace('v1.9.3','v1.10.1').replace('v1.1.0','v1.2.0'))
    (h/'go.sum').write_bytes((mod/'go.sum').read_bytes())
    p=h/'main.go';s=p.read_text()
    for old,new in [('var duration = flag.Duration("duration", 0, "measurement duration after setup; zero runs one batch")','var forks=flag.Int("forks",12,"fresh DBs")'),('deadline := time.Now().Add(*duration)',''),('time.Now().After(deadline)','i+1>=*forks')]:
        assert s.count(old)==1
        s=s.replace(old,new)
    p.write_text(s)
    exe=tmp/arm
    subprocess.run(['go','build','-mod=readonly','-p','2','-trimpath','-buildvcs=false','-o',exe,'.'],cwd=h,env=env,check=True)
    meta[arm]=dict(source_commit=ref,sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),go=subprocess.check_output(['go','version','-m',exe],text=True))
(out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
