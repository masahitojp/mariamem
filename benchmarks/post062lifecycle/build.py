from pathlib import Path
import subprocess,sys,json,hashlib,os,tarfile,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit,ReleasePin,verify_release_pin
from experiment_disk import DiskGuard,run_guarded
plan=json.loads((b/'plan.json').read_text());h=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()
require_commit(s,h);require_commit(s,plan['candidate_source_commit']);verify_release_pin(s,ReleasePin(**plan['baseline']))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
changed=subprocess.check_output(['git','diff','--name-only',plan['candidate_source_commit'],h],cwd=s,text=True).splitlines();assert changed and all(n.startswith('benchmarks/') for n in changed),changed
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
archive=t/'baseline.tar';subprocess.run(['git','archive','--format=tar','--output',str(archive),plan['baseline']['source_commit']],cwd=s,check=True)
baseline=t/'baseline';baseline.mkdir()
with tarfile.open(archive) as f:
 for member in f.getmembers():
  assert not member.name.startswith('/') and '..' not in Path(member.name).parts and (member.isfile() or member.isdir()),member.name
 f.extractall(baseline)
archive_sha=sha(archive);archive.unlink()
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
inputs={'harness_source_commit':h,'plan_sha256':sha(b/'plan.json'),'baseline_archive_sha256':archive_sha,'binaries':{},'observer_source':'d05cd878e77828b8c8b6025f4026a335b14912ce','go':'go1.27.3'}
guard=DiskGuard(w,12,7)
for variant,source in [('baseline',baseline),('current',s),('diagnostic',s)]:
 mod=t/(variant+'.mod');mod.write_text((b/'go.mod').read_text().replace('=> ../..','=> '+str(source)))
 mod.with_suffix('.sum').write_bytes((b/'go.sum').read_bytes())
 flags=['-modfile',str(mod),'-mod=readonly']
 if variant=='diagnostic':
  subprocess.run([sys.executable,str(s/'benchmarks/undorelay/overlay.py'),str(s),str(t/'undo-overlay')],check=True)
  flags+=['-overlay',str(t/'undo-overlay/overlay.json')]
  with (e/'observer-unit.txt').open('w') as log:
   code=run_guarded(['go','test','-p','1','-count=1','-overlay',str(t/'undo-overlay/overlay.json'),'-run','TestUW|TestUO|TestUR','./internal/generatedgo/code/base'],guard,cwd=s,env=env,output=log,timeout=1200)
  assert code==0,('observer unit',code)
  inputs['observer_overlay']=json.loads((t/'undo-overlay/hashes.json').read_text())
 command=['go','build','-p','1','-trimpath','-buildvcs=true']+flags+['-o',str(t/variant),'./maria']
 at=time.monotonic()
 with (e/(variant+'-build.txt')).open('w') as log:code=run_guarded(command,guard,cwd=b,env=env,output=log,timeout=1200)
 assert code==0,(variant,code)
 info=subprocess.check_output(['go','version','-m',str(t/variant)],env=env,text=True)
 assert 'vcs.revision='+h in info and 'vcs.modified=false' in info,info
 assert str(source) in info,info
 product=plan['baseline']['source_commit'] if variant=='baseline' else plan['candidate_source_commit']
 inputs['binaries'][variant]={'sha256':sha(t/variant),'product_source_commit':product,'guest_sha256':json.loads((source/'release/generated-go-inputs.json').read_text())['guest_sha256'],'build_info':info.replace(str(w),'<WORKSPACE>'),'build_seconds':time.monotonic()-at}
 (e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 print('BUILT',variant,round(time.monotonic()-at,1),'seconds',flush=True)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
