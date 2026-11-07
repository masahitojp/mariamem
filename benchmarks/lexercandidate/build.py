from pathlib import Path
import subprocess,sys,os,json,hashlib,time
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit,verify_go_binary
from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,head)
plan=json.loads((b/'plan.json').read_text());require_commit(s,plan['product_source_commit'])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert all(n.startswith('benchmarks/') for n in subprocess.check_output(['git','diff','--name-only',plan['product_source_commit'],head],cwd=s,text=True).splitlines())
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LEXER'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
guard=DiskGuard(w,12,10)
record={'source_commit':head,'product_source_commit':plan['product_source_commit'],'guest_sha256':plan['guest_sha256'],'plan_sha256':sha(b/'plan.json'),'binaries':{}}
mod=t/'probe.mod';mod.write_text((b/'go.mod').read_text().replace('=> ../..','=> '+str(s)));mod.with_suffix('.sum').write_bytes((b/'go.sum').read_bytes())
for variant in ['diagnostic']:
 overlay=t/('overlay-'+variant)
 subprocess.run([sys.executable,str(b/'overlay.py'),str(s),str(overlay)],check=True)
 with (e/(variant+'-unit.txt')).open('w') as log:
  code=run_guarded(['go','test','-p','1','-count=1','-overlay',str(overlay/'overlay.json'),'-run','^TestLP|TestUW|TestUO|TestUR','./internal/generatedgo/code/base'],guard,cwd=s,env=env,output=log,timeout=1200)
 assert code==0,('unit',variant,code)
 at=time.monotonic()
 with (e/(variant+'-build.txt')).open('w') as log:
  code=run_guarded(['go','build','-p','1','-trimpath','-buildvcs=true','-modfile',str(mod),'-mod=readonly','-overlay',str(overlay/'overlay.json'),'-o',str(t/variant),'.'],guard,cwd=b,env=env,output=log,timeout=1200)
 assert code==0,('build',variant,code)
 info=subprocess.check_output(['go','version','-m',str(t/variant)],env=env,text=True)
 assert 'vcs.revision='+head in info and 'vcs.modified=false' in info and str(s) in info
 record['binaries'][variant]={'sha256':sha(t/variant),'build_info':info.replace(str(w),'<WORKSPACE>'),'overlay':json.loads((overlay/'hashes.json').read_text()),'build_seconds':time.monotonic()-at}
 (e/'inputs.json').write_text(json.dumps(record,indent=2)+'\n')
 print('BUILD PASS',variant,round(time.monotonic()-at,1),flush=True)
