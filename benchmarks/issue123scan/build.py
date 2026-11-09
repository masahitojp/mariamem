from pathlib import Path
import subprocess,sys,json,hashlib,os,tarfile,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit,ReleasePin,verify_release_pin
plan=json.loads((b/'plan.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()
require_commit(s,head);require_commit(s,plan['parent_source_commit'])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
changed=subprocess.check_output(['git','diff','--name-only',plan['parent_source_commit'],head],cwd=s,text=True).splitlines()
assert all(p.startswith('benchmarks/issue123scan/') or p in ['benchmarks/staticimage/image.go','benchmarks/staticimage/image_test.go'] for p in changed),changed
for path,digest in plan['source_hashes'].items():assert sha(s/path)==digest,path
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_','LEXER_','PYTEST'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
inputs={'harness_and_candidate_source_commit':head,'plan':plan,'binaries':{},'archives':{},'runtime_delta_paths':changed}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
def run(name,args,cwd=s,timeout=1200):
 print(name,flush=True)
 with (e/(name+'.txt')).open('w') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 assert r.returncode==0,(name,r.returncode)
run('mapping-unit',['go','test','-p','1','-count=1','-v','-run','TestMapping|TestStaticPages','./internal/generatedgo/code/base'])
run('constructor-unit',['go','test','-p','1','-count=1','-v','./benchmarks/staticimage'])
mod=t/'probe.mod';mod.write_text((s/'benchmarks/issue123baseline/go.mod').read_text().replace('=> ../..','=> '+str(s)));mod.with_suffix('.sum').write_bytes((s/'benchmarks/issue123baseline/go.sum').read_bytes())
at=time.monotonic()
run('probe-build',['go','build','-p','1','-trimpath','-buildvcs=true','-modfile',str(mod),'-mod=readonly','-tags','issue123image','-o',str(t/'bin-probe'),'./maria'],cwd=s/'benchmarks/issue123baseline')
info=subprocess.check_output(['go','version','-m',str(t/'bin-probe')],env=env,text=True)
assert 'vcs.revision='+head in info and 'vcs.modified=false' in info
inputs['binaries']['probe']={'sha256':sha(t/'bin-probe'),'source_commit':head,'guest_sha256':json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256'],'build_info':info.replace(str(w),'<WORKSPACE>'),'build_seconds':time.monotonic()-at}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
