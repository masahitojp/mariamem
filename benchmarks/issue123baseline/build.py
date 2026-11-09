from pathlib import Path
import subprocess,sys,json,hashlib,os,tarfile,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit,ReleasePin,verify_release_pin
plan=json.loads((b/'plan.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()
require_commit(s,head);require_commit(s,plan['product_source_commit']);verify_release_pin(s,ReleasePin(**plan['baseline']))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
allowed=['internal/generatedgo/static_image_experiment.go','internal/generatedgo/memory_backing_unix.go','internal/generatedgo/code/base/static_pages_experiment.go','internal/generatedgo/code/base/static_pages_experiment_test.go']
changed=subprocess.check_output(['git','diff','--name-only',plan['product_source_commit'],head],cwd=s,text=True).splitlines()
assert all(p.startswith('benchmarks/') or p in allowed for p in changed),changed
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(s/'internal/generatedgo/code/generated.go')==plan['generated_source_sha256']
assert json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256']==plan['guest_sha256']
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_','LEXER_','PYTEST'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
inputs={'harness_and_candidate_source_commit':head,'plan':plan,'binaries':{},'archives':{},'runtime_delta_paths':allowed}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
def run(name,args,cwd=s,timeout=1200):
 print(name,flush=True)
 with (e/(name+'.txt')).open('w') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 assert r.returncode==0,(name,r.returncode)
run('mapping-unit',['go','test','-p','1','-count=1','-v','-run','TestMapping|TestStaticPages','./internal/generatedgo/code/base'])
run('constructor-unit',['go','test','-p','1','-count=1','-v','./benchmarks/staticimage'])
for variant,commit in [('baseline',plan['baseline']['source_commit']),('current',plan['product_source_commit']),('pages',head)]:
 source=s
 if variant!='pages':
  archive=t/(variant+'.tar');subprocess.run(['git','archive','--format=tar','--output',str(archive),commit],cwd=s,check=True);inputs['archives'][variant]=sha(archive)
  source=t/variant;source.mkdir()
  with tarfile.open(archive) as f:
   assert all(not m.name.startswith('/') and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()) for m in f.getmembers())
   f.extractall(source)
  archive.unlink()
 mod=t/(variant+'.mod');mod.write_text((b/'go.mod').read_text().replace('=> ../..','=> '+str(source)));mod.with_suffix('.sum').write_bytes((b/'go.sum').read_bytes())
 flags=['-modfile',str(mod),'-mod=readonly'];flags+=['-tags','issue123image'] if variant=='pages' else []
 at=time.monotonic();run(variant+'-build',['go','build','-p','1','-trimpath','-buildvcs=true']+flags+['-o',str(t/('bin-'+variant)),'./maria'],cwd=b)
 info=subprocess.check_output(['go','version','-m',str(t/('bin-'+variant))],env=env,text=True)
 assert 'vcs.revision='+head in info and 'vcs.modified=false' in info
 assert str(source) in info
 inputs['binaries'][variant]={'sha256':sha(t/('bin-'+variant)),'source_commit':commit,'guest_sha256':json.loads((source/'release/generated-go-inputs.json').read_text())['guest_sha256'],'build_info':info.replace(str(w),'<WORKSPACE>'),'build_seconds':time.monotonic()-at}
 (e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 print('BUILT',variant,round(time.monotonic()-at,1),flush=True)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
