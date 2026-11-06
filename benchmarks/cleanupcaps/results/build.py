from pathlib import Path
import json,subprocess,sys,os,hashlib,time
w=Path(__file__).resolve().parents[1];t=w/'temp';s=w/'worktree';e=w/'evidence';b=s/'benchmarks/forkcompare';sys.path.insert(0,str(s/'scripts'));from git_identity import require_commit;from experiment_disk import DiskGuard,run_guarded
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();require_commit(s,head);assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True);require_commit(s,'1862f4a89397bddfa1820d835106d3437a438cf7')
changed=subprocess.check_output(['git','diff','--name-only','1862f4a8',head],cwd=s,text=True).splitlines();assert all(n.startswith(('benchmarks/forkcompare/','benchmarks/forkstages/','benchmarks/defaultsettings/','benchmarks/bufferloadoff/','benchmarks/bufferbothoff/','benchmarks/bufferflush/','benchmarks/updatecapture/','benchmarks/updatenotify/','benchmarks/undoowner/','benchmarks/undorelay/','benchmarks/cleanupwait/','benchmarks/cleanupnotify/','benchmarks/cleanupcaps/')) for n in changed),changed
for n in ['cache','modcache','gotmp','scratch']:(t/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG'))};env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.27.3 darwin/arm64'
subprocess.run(['python3',str(s/'benchmarks/cleanupnotify/overlay.py'),str(s),str(t/'overlay')],check=True)
guard=DiskGuard(w,12,6);start=time.monotonic()
with (e/'cap-unit.log').open('w') as log:
 code=run_guarded(['go','test','-count=1','-run','TestResolveMaxForks|TestUpdateGuestLabelBinding|TestUpdateExecWindow','./probe'],guard,cwd=b,env=env,output=log,timeout=120)
assert code==0,('cap units',code)
print('CAP RESOLVER UNITS PASS; runtime receipt reuse separate',flush=True)
with (e/'build.log').open('w') as log:
 code=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(t/'overlay/overlay.json'),'-o',str(t/'probe'),'./maria'],guard,cwd=b,env=env,output=log,timeout=1200)
assert code==0,code
info=subprocess.check_output(['go','version','-m',str(t/'probe')],env=env,text=True);assert 'vcs.revision='+head in info and 'vcs.modified=false' in info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={'product_source_commit':'1862f4a89397bddfa1820d835106d3437a438cf7','harness_source_commit':head,'origin_guest_sha256':json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256'],'binary_sha256':sha(t/'probe'),'toolchain':version,'buildinfo':info.replace(str(w),'<WORKSPACE>'),'overlay':json.loads((t/'overlay/hashes.json').read_text()),'build_seconds':time.monotonic()-start}
assert inputs['origin_guest_sha256']=='6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe'
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print('BUILD PASS',head,flush=True)

prior=json.loads((e/'prior-inputs.json').read_text())
assert inputs['overlay']==prior['overlay'],'runtime overlay changed'
assert inputs['origin_guest_sha256']==prior['origin_guest_sha256']
changed_runtime=subprocess.check_output(['git','diff','--name-only','c37d578e',head,'--','.',':(exclude)benchmarks/**'],cwd=s,text=True).splitlines();assert not changed_runtime,changed_runtime
(e/'verification-reuse.json').write_text(json.dumps({'status':'REUSED_RUNTIME_SOURCE_AND_OVERLAY_NEW_HARNESS','original_report_commit':'6f780e5a7a44022e0f5c2c7bef888a233f821795','original_runtime_source_commit':'c37d578e68b3068173a6734b38f00e11782cb123','new_harness_source_commit':head,'binary_sha256_equal':inputs['binary_sha256']==prior['binary_sha256'],'prior_binary_sha256':prior['binary_sha256'],'new_binary_sha256':inputs['binary_sha256'],'runtime_source_changed':False,'guest_changed':False,'measurement_changes':'Independent cap CLI/readback and ready/disposed markers; cap4 remeasured in same binary','scope':'Original focused unit/host race results remain at original SHA; new measurement resolver unit executed'},indent=2)+'\n')
print('RUNTIME/OVERLAY REUSE VERIFIED; NEW HARNESS',flush=True)
