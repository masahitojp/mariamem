from pathlib import Path
import json,subprocess,sys,os,hashlib,time
w=Path(__file__).resolve().parents[1];t=w/'temp';e=w/'evidence';s=w/'worktree';sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit
from experiment_disk import DiskGuard,run_guarded
plan=json.loads((e/'plan.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,head);assert not subprocess.check_output(['git','status','--porcelain'],cwd=s).strip()
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG'))};env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version==plan['fixed']['toolchain'];guard=DiskGuard(w,12,8);out={'controller_source_commit':head,'arms':{},'toolchain':version,'product_source_commit':plan['product_source_commit'],'guest_sha256':plan['guest_sha256']}
for arm,a in plan['arms'].items():
 src=t/arm;require_commit(src,a['source_commit']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip()==a['source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=src).strip()
 changed=subprocess.check_output(['git','diff','--name-only',plan['product_source_commit'],a['source_commit']],cwd=src,text=True).splitlines();assert all(n.startswith('benchmarks/') for n in changed)
 assert json.loads((src/'release/generated-go-inputs.json').read_text())['guest_sha256']==plan['guest_sha256']
 ov=t/(arm+'-overlay');start=time.monotonic();subprocess.run(['python3',str(src/a['overlay']),str(src),str(ov)],check=True)
 with (e/(arm+'-unit.log')).open('w') as log:code=run_guarded(['go','test','-count=1','-run','TestBufferLoadSelector|TestUW|TestUO','-overlay',str(ov/'overlay.json'),'./internal/generatedgo/code/base'],guard,cwd=src,env=env,output=log,timeout=120)
 assert code==0,(arm,'unit',code)
 binary=t/(arm+'-probe')
 with (e/(arm+'-build.log')).open('w') as log:code=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(ov/'overlay.json'),'-o',str(binary),'./maria'],guard,cwd=src/'benchmarks/forkcompare',env=env,output=log,timeout=1200)
 assert code==0,(arm,'build',code)
 info=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True);assert 'vcs.revision='+a['source_commit'] in info and 'vcs.modified=false' in info
 digest=hashlib.sha256(binary.read_bytes()).hexdigest();out['arms'][arm]={'source_commit':a['source_commit'],'binary_sha256':digest,'prior_binary_sha256':a['prior_binary_sha256'],'prior_binary_byte_match':digest==a['prior_binary_sha256'],'buildinfo':info.replace(str(w),'<WORKSPACE>'),'overlay':json.loads((ov/'hashes.json').read_text()),'build_seconds':time.monotonic()-start}
 (e/'inputs.json').write_text(json.dumps(out,indent=2)+'\n');print(arm,'BUILD PASS','prior binary byte match',digest==a['prior_binary_sha256'],flush=True)
