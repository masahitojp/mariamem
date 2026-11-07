from pathlib import Path
import os,sys,json,subprocess,hashlib,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit
from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
h=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,h)
plan=json.loads((b/'plan.json').read_text());require_commit(s,plan['baseline_source_commit'])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
changed=subprocess.check_output(['git','diff','--name-only',plan['baseline_source_commit'],h],cwd=s,text=True).splitlines()
assert all(p.startswith('benchmarks/') or p=='docs/internals/startup-lifecycle.md' or p.startswith('docs/reviews/innodb-startup-source/') or p in ['internal/generatedgo/static_image_experiment.go','internal/generatedgo/memory_backing_unix.go','internal/generatedgo/code/base/static_image_experiment.go','internal/generatedgo/code/base/static_image_experiment_test.go','internal/generatedgo/code/base/static_pages_experiment.go','internal/generatedgo/code/base/static_pages_experiment_test.go'] for p in changed)
assert json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256']==plan['guest_sha256']
for n in ['cache','modcache','gotmp','scratch','trace']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
guard=DiskGuard(w,12,8)
inputs={'source_commit':h,'baseline_source_commit':plan['baseline_source_commit'],'guest_sha256':plan['guest_sha256'],'plan_sha256':sha(b/'plan.json'),'toolchain':subprocess.check_output(['go','version'],env=env,text=True).strip(),'binaries':{}}
assert inputs['toolchain']=='go version go1.27.3 darwin/arm64'
with (e/'wave-unit.log').open('w') as log:
 rc=run_guarded(['go','test','-race','-trimpath','-count=1','./benchmarks/staticimageruntime/probe'],guard,cwd=s,env=dict(env,CGO_ENABLED='1'),output=log,timeout=180)
assert rc==0,('wave units',rc)
for variant in ['diagnostic']:
 flags=[]
 if variant=='diagnostic':
  subprocess.run([sys.executable,str(s/'benchmarks/trxstartupsplit/overlay.py'),str(s),str(t/'overlay')],check=True)
  flags=['-overlay',str(t/'overlay/overlay.json')]
  with (e/'observer-unit.log').open('w') as log:rc=run_guarded(['go','test','-trimpath','-p','1','-count=1']+flags+['-run','TestUW|TestUO|TestUR|TestOpenSpan|TestRemainder|TestTrxSplit','./internal/generatedgo/code/base'],guard,cwd=s,env=env,output=log,timeout=1200)
  assert rc==0,('observer',rc)
  inputs['overlay']=json.loads((t/'overlay/hashes.json').read_text())
 at=time.monotonic()
 with (e/(variant+'-build.log')).open('w') as log:rc=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true']+flags+['-o',str(t/variant),'./benchmarks/staticimageruntime/maria'],guard,cwd=s,env=env,output=log,timeout=1200)
 assert rc==0,(variant,rc)
 info=subprocess.check_output(['go','version','-m',str(t/variant)],env=env,text=True)
 assert 'vcs.revision='+h in info and 'vcs.modified=false' in info
 inputs['binaries'][variant]={'sha256':sha(t/variant),'build_info':info.replace(str(w),'<WORKSPACE>'),'build_seconds':time.monotonic()-at}
 (e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 print('BUILT',variant,flush=True)
