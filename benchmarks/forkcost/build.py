from pathlib import Path
import hashlib,json,os,subprocess,sys,time
W=Path(__file__).resolve().parents[1];T=W/'temp';S=T/'source';G=T/'pgmem';E=W/'evidence';B=S/'benchmarks/forkcompare'
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit,verify_release_pin,ReleasePin
from experiment_disk import DiskGuard,run_guarded
def git(d,*a):return subprocess.check_output(['git',*a],cwd=d,text=True).strip()
plan=json.loads((E/'plan.json').read_text());head=git(S,'rev-parse','HEAD');require_commit(S,head);require_commit(S,plan['product_source_commit'])
assert not git(S,'status','--porcelain') and all(p.startswith(('benchmarks/forkcompare/','benchmarks/forkcost/')) for p in git(S,'diff','--name-only',plan['product_source_commit'],head).splitlines())
verify_release_pin(G,ReleasePin(**plan['pgmem']));assert git(G,'rev-parse','HEAD')==plan['pgmem']['source_commit'] and not git(G,'status','--porcelain')
assert {x.split()[0] for x in git(G,'ls-remote','origin','refs/tags/v1.18.2','refs/tags/v1.18.2^{}').splitlines()}=={plan['pgmem']['source_commit'],plan['pgmem']['tag_object_sha']}
assert json.loads((S/'release/generated-go-inputs.json').read_text())['guest_sha256']==plan['guest_sha256']
for n in ['cache','modcache','gotmp','scratch','bin']:(T/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','FORKCOST_','FORKSTAGES_','GODEBUG'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'cache'),GOMODCACHE=str(T/'modcache'),GOTMPDIR=str(T/'gotmp'),TMPDIR=str(T/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.4 darwin/arm64'
subprocess.run([sys.executable,E/'overlay.py',S,G,T/'overlay'],check=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={'harness_source_commit':head,'product_source_commit':plan['product_source_commit'],'pgmem':plan['pgmem'],'guest_sha256':plan['guest_sha256'],'toolchain':'go1.27.4','overlay':json.loads((T/'overlay/hashes.json').read_text()),'binaries':{}}
guard=DiskGuard(W,12,12)
for label,package in [('maria','maria'),('pgmem','postgres')]:
 at=time.monotonic();binary=T/'bin'/label
 with (E/('build-'+label+'.txt')).open('w') as log:
  code=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(T/'overlay/overlay.json'),'-o',str(binary),'./'+package],guard,cwd=B,env=env,output=log,timeout=1200)
 assert code==0,(label,code)
 info=subprocess.check_output(['go','version','-m',binary],env=env,text=True)
 assert 'vcs.revision='+head in info and 'vcs.modified=false' in info and 'CGO_ENABLED=0' in info
 inputs['binaries'][label]={'sha256':sha(binary),'build_seconds':time.monotonic()-at,'buildinfo':info.replace(str(W),'<WORKSPACE>')}
 (E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(label,'BUILD PASS',flush=True)
(E/'build-complete.json').write_text(json.dumps({'result':'PASS','peak_owned_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free})+'\n')
