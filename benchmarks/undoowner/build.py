from pathlib import Path
import json,subprocess,sys,os,hashlib,time
w=Path(__file__).resolve().parents[1];t=w/'temp';s=w/'worktree';e=w/'evidence';b=s/'benchmarks/forkcompare';sys.path.insert(0,str(s/'scripts'));from git_identity import require_commit;from experiment_disk import DiskGuard,run_guarded
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,head);assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True);require_commit(s,'1862f4a89397bddfa1820d835106d3437a438cf7')
changed=subprocess.check_output(['git','diff','--name-only','1862f4a8',head],cwd=s,text=True).splitlines();assert all(n.startswith(('benchmarks/forkcompare/','benchmarks/forkstages/','benchmarks/defaultsettings/','benchmarks/bufferloadoff/','benchmarks/bufferbothoff/','benchmarks/bufferflush/','benchmarks/updatecapture/','benchmarks/updatenotify/','benchmarks/undoowner/')) for n in changed),changed
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG'))};env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.27.3 darwin/arm64'
subprocess.run(['python3',str(s/'benchmarks/undoowner/overlay.py'),str(s),str(t/'overlay')],check=True)
guard=DiskGuard(w,12,6);start=time.monotonic()
with (e/'selector-unit.log').open('w') as log:
 code=run_guarded(['go','test','-count=1','-run','TestBufferLoadSelector|TestUW|TestUO','-overlay',str(t/'overlay/overlay.json'),'./internal/generatedgo/code/base'],guard,cwd=s,env=env,output=log,timeout=120)
assert code==0,('selector unit',code)
with (e/'observer-unit.log').open('w') as log:
 code=run_guarded(['go','test','-count=1','-run','TestUpdateGuestLabelBinding|TestUpdateExecWindow','./probe'],guard,cwd=b,env=env,output=log,timeout=120)
assert code==0,('observer unit',code)
print('SELECTOR AND OBSERVER UNITS PASS',flush=True)
with (e/'build.log').open('w') as log:
 code=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(t/'overlay/overlay.json'),'-o',str(t/'probe'),'./maria'],guard,cwd=b,env=env,output=log,timeout=1200)
assert code==0,code
info=subprocess.check_output(['go','version','-m',str(t/'probe')],env=env,text=True);assert 'vcs.revision='+head in info and 'vcs.modified=false' in info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={'product_source_commit':'1862f4a89397bddfa1820d835106d3437a438cf7','harness_source_commit':head,'origin_guest_sha256':json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256'],'binary_sha256':sha(t/'probe'),'toolchain':version,'buildinfo':info.replace(str(w),'<WORKSPACE>'),'overlay':json.loads((t/'overlay/hashes.json').read_text()),'build_seconds':time.monotonic()-start}
assert inputs['origin_guest_sha256']=='6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe'
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print('BUILD PASS',head,flush=True)
