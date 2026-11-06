from pathlib import Path
import subprocess,sys,json,hashlib,os,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit
from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((b/'plan.json').read_text());h=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()
require_commit(s,h);require_commit(s,plan['product_source_commit'])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
changed=subprocess.check_output(['git','diff','--name-only',plan['product_source_commit'],h],cwd=s,text=True).splitlines();assert changed and all(n.startswith('benchmarks/') for n in changed),changed
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.27.3 darwin/arm64'
subprocess.run([sys.executable,str(b/'overlay.py'),str(s),str(t/'overlay')],check=True)
guard=DiskGuard(w,12,8)
with (e/'observer-unit.txt').open('w') as log:
 code=run_guarded(['go','test','-p','1','-count=1','-overlay',str(t/'overlay/overlay.json'),'-run','TestUW|TestUO|TestUR','./internal/generatedgo/code/base'],guard,cwd=s,env=env,output=log,timeout=1200)
assert code==0,('observer',code)
at=time.monotonic()
with (e/'build.txt').open('w') as log:
 code=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(t/'overlay/overlay.json'),'-o',str(t/'probe'),'./maria'],guard,cwd=b,env=env,output=log,timeout=1200)
assert code==0,('build',code)
info=subprocess.check_output(['go','version','-m',str(t/'probe')],env=env,text=True);assert 'vcs.revision='+h in info and 'vcs.modified=false' in info
inputs={'product_source_commit':plan['product_source_commit'],'harness_source_commit':h,'guest_sha256':json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256'],'binary_sha256':sha(t/'probe'),'toolchain':version,'build_info':info.replace(str(w),'<WORKSPACE>'),'overlay':json.loads((t/'overlay/hashes.json').read_text()),'build_seconds':time.monotonic()-at,'plan_sha256':sha(b/'plan.json')}
assert inputs['guest_sha256']==plan['guest_sha256']
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print('BUILD PASS',h,flush=True)
