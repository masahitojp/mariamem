#!/usr/bin/env python3
"""Identity-bound bounded native checks for the owned-root guest spike."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
GO=Path('/Users') / os.environ['USER'] / '.go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin/go'

def environment(w):
    temp=w/'temp'
    for n in ('gocache','gopath','gomodcache','gotmp'):(temp/n).mkdir(parents=True,exist_ok=True)
    e=dict(os.environ,GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',
           GOCACHE=str(temp/'gocache'),GOPATH=str(temp/'gopath'),GOMODCACHE=str(temp/'gomodcache'),
           GOTMPDIR=str(temp/'gotmp'),TMPDIR=str(temp/'gotmp'),CGO_ENABLED='0',GOPROXY='off',GOSUMDB='off',
           PATH=str(GO.parent)+os.pathsep+os.environ['PATH'],MARIAMEM_GO_CACHE_ROOT=str(temp/'feedback-cache'))
    for k in ('GOGC','GOMEMLIMIT','GOMAXPROCS','MARIAMEM_TIMING_DIR','MARIAMEM_NATIVE_DIR','MARIAMEM_TEST_HOST'):e.pop(k,None)
    return e

def modules(env):
    old=GO.parents[4]
    # Existing cache is read-only input; private copies are verified against zip hashes.
    cache=Path('/Users')/os.environ['USER']/'.go/pkg/mod'
    for name,version in [('github.com/go-sql-driver/mysql','v1.9.3'),('filippo.io/edwards25519','v1.1.0')]:
        source=cache/(name+'@'+version);dest=Path(env['GOMODCACHE'])/(name+'@'+version)
        if not dest.exists():shutil.copytree(source,dest)
        source=cache/'cache/download'/name/'@v';dest=Path(env['GOMODCACHE'])/'cache/download'/name/'@v';dest.mkdir(parents=True,exist_ok=True)
        for p in source.glob(version+'.*'):
            if p.suffix!='.lock':shutil.copy2(p,dest/p.name)

def clean(text,w):
    return re.sub(r'/(?:Users|home)/[^\s/]+/','<user>/',text.replace(str(ROOT),'<source>').replace(str(w/'temp'),'<temp>'))

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['focused','integration','public','python','source','regenerate']);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--guest-dir',type=Path);a=p.parse_args();w=a.workspace.resolve();env=environment(w)
    identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=ROOT))
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip(),'Commit exact inputs first'
    version=subprocess.check_output([str(GO),'version'],env=env,text=True).strip();assert 'go1.26.8' in version
    result={'source_commit':identity['source_commit'],'stage':a.stage,'go':version,'runs':[]}
    if a.stage in ('focused','integration','public','python'):modules(env)
    if a.stage=='focused':
        commands=[('modules',[str(GO),'mod','verify']),('focused',[str(GO),'test','-json','-race','-p','1','-count=1','-timeout=120s','./internal/prepared','./internal/snapshot','./internal/generatedgo/code/base'])];env['CGO_ENABLED']='1'
    elif a.stage=='integration':
        env['MARIAMEM_TEST_DEFAULT']='1';commands=[('integration',[str(GO),'test','-json','-p','1','-tags=integration','./tests/gointegration','-count=1','-timeout=240s','-run','TestPublicLifecycle|TestOwnedManyOrderParallelAndClose|TestOwnedForkCloseRace|TestOwnedModifiedChildCreatesNewBaseline'])]
    elif a.stage=='public':
        commands=[('public-api',[str(GO),'test','-json','-p','1','-count=1','./internal/guest','./internal/host','./internal/control','.'])]
    elif a.stage=='python':
        host=w/'temp/owned-root-host';env.update(PYTHONPATH=str(ROOT/'python'),MARIAMEM_TEST_HOST=str(host),PYTHONDONTWRITEBYTECODE='1')
        commands=[('python-host-build',[str(GO),'build','-p','1','-trimpath','-o',str(host),'./cmd/mariamem-host']),('python-owned',[sys.executable,'-m','pytest','tests/test_owned_snapshot.py::test_modified_child_creates_new_baseline_without_changing_parent','tests/test_owned_snapshot.py::test_explicit_other_binary_uses_private_handoff','tests/test_owned_snapshot.py::test_real_fork_racing_baseline_close_preserves_started_children','-q'])]
    elif a.stage=='source':
        commands=[('source',[sys.executable,'scripts/verify_generated_runtime.py']),('source-tests',[sys.executable,'-m','pytest','tests/test_generated_runtime_inventory.py','tests/test_distribution_licenses.py','tests/test_packaging_license_mirrors.py','-q'])]
    else:
        assert a.guest_dir
        env.update(GOPROXY='https://proxy.golang.org',GOSUMDB='sum.golang.org')
        commands=[('regeneration',[sys.executable,'scripts/regenerate_release_guest.py','--guest-dir',str(a.guest_dir.resolve()),'--output',str(w/'temp/regeneration')])]
    evidence=w/'evidence';evidence.mkdir(exist_ok=True)
    for label,cmd in commands:
        start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1500)
        text=clean(r.stdout,w);(evidence/(label+'.txt')).write_text(text)
        item={'name':label,'arguments':[Path(cmd[0]).name,*[clean(x,w) for x in cmd[1:]]],'exit_code':r.returncode,'seconds':time.monotonic()-start};result['runs'].append(item)
        (evidence/(a.stage+'-receipt.json')).write_text(json.dumps(result,indent=2)+'\n');print(label,'PASS' if not r.returncode else 'FAIL',flush=True)
        if r.returncode:print(text[-6000:],flush=True);return r.returncode
    return 0
if __name__=='__main__':raise SystemExit(main())
