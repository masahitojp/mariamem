from pathlib import Path
import os,sys,json,subprocess,shutil
W=Path('/exp/worktree');X=Path('/exp');sys.path.insert(0,str(W/'scripts'))
from common import digest
from dev_guest import source_identity,CONTRACT
from install_guest_toolchain import inventory
from build_feedback import run
sdk=Path('/root/.wasixcc');pins=json.loads((W/'release/generated-go-toolchain.json').read_text());prepared=json.loads((W/'build/prepared-source.json').read_text());identity=source_identity(W)
assert prepared['inputs_lock_sha256']==digest(W/'release/inputs.lock.json')
assert prepared['overlays']=={p.name:digest(p) for p in (W/'guest').iterdir() if p.is_file()}
for key,pin in pins['archives'].items():assert digest(W/'build/downloads'/pin['file'])==pin['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith('WASIXCC_')};env.update(PATH=str(sdk/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(sdk/'llvm/lib'),LC_ALL='C',TZ='UTC',SOURCE_DATE_EPOCH='0')
commands={'wasixcc':[sdk/'bin/wasixccenv','--version'],'llvm':[sdk/'llvm/bin/clang','--version'],'lld':[sdk/'llvm/bin/wasm-ld','--version'],'binaryen':[sdk/'binaryen/bin/wasm-opt','--version'],'cmake':['cmake','--version'],'bison':['bison','--version'],'make':['make','--version'],'python':[sys.executable,'--version']}
versions={k:subprocess.check_output(v,env=env,text=True).strip() for k,v in commands.items()};assert '23.1.0' in versions['llvm'] and 'version 133' in versions['binaryen']
toolchain={'contract':'generated-go-v1','pins_sha256':digest(W/'release/generated-go-toolchain.json'),'host':'linux-arm64','versions':versions,'sysroot':inventory(sdk/'sysroot'),'archives_sha256':{k:v['sha256'] for k,v in pins['archives'].items()},'environment':{k:env[k] for k in ('PATH','LD_LIBRARY_PATH','LC_ALL','TZ','SOURCE_DATE_EPOCH')}}
source=W/'build/source';assert source.exists() and not Path('/work/source').exists()
run([sys.executable,W/'tests/buffer_pool_alignment_check.py','--source',source,'--output',X/'evidence/buffer-pool-contract.json'],env=env,check=True,phase='spike:resumed-source-contract',inputs=[W/'tests/buffer_pool_alignment_check.py',W/'guest/experimental.patch'],tools=versions)
shutil.move(str(source),'/work/source');shell=W/'benchmarks/spikes/wasm2go/legacy_eh_toolchain.sh';linked=Path('/work/artifact/mariamem-legacy-eh.wasm');guest=Path('/work/artifact/mariamem-legacy-eh-O2-compatible.wasm')
run(['bash',shell,'build-no-postopt'],env=env,check=True,phase='spike:compile-link',inputs=[W/'guest/experimental.patch',W/'build/prepared-source.json'],outputs=[linked],tools=versions)
run(['bash',shell,'postopt'],env=env,check=True,phase='spike:postopt',inputs=[linked],outputs=[guest],tools=versions)
out=X/'temp/guest';out.mkdir()
shutil.copy2(guest,out/'mariamem.wasm');shutil.copy2(linked,out/'linked.wasm')
for n in ['link.txt','flags.make','CMakeCache.txt']:shutil.copy2(linked.parent/n,out/n)
cmd=[sdk/'binaryen/bin/wasm-opt','-O2','--enable-threads','--enable-mutable-globals','--enable-bulk-memory','--enable-bulk-memory-opt','--enable-exception-handling','--enable-simd','--enable-relaxed-simd','--enable-extended-const','--print-function-map',linked,'-o',X/'temp/mapped.wasm']
with (X/'evidence/function-map.txt').open('w') as f:subprocess.run(cmd,env=env,stdout=f,check=True)
assert digest(X/'temp/mapped.wasm')==digest(guest)
record={'contract':CONTRACT,'result':'UNQUALIFIED','source_commit':identity['commit'],'source_identity':identity,'guest_sha256':digest(guest),'guest_bytes':guest.stat().st_size,'repetitions':[{'guest_sha256':digest(guest),'linked_sha256':digest(linked)}],'prepared_source':prepared,'toolchain':toolchain,'canonical_build_sha256':digest(W/'release/generated-go-build.json'),'experiment_resume':'SDK/source preparation from first clean stage; exact pinned inputs reverified before C compilation; prior failure only source-shape check'}
assert source_identity(W)==identity
(out/'guest.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print('PASS experimental C guest:',record['guest_sha256'],flush=True)
