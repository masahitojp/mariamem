"""Isolated installation and four fixed runners; canonical adapters stay unchanged."""
from pathlib import Path
import hashlib,importlib.util,json,os,shutil,subprocess,sys,tarfile,time
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
B=json.loads((H/'bindings.json').read_text());ORIGIN=T/'origin';BASE='8df45792a927e440972266ee799d6f7223713e14';HARNESS='d24087eedd21c6384c231fb119c8e98da7b370aa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def git(*a):return subprocess.check_output(['git',*a],cwd=S,text=True).strip()
def inventory(p):return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file()}
assert not git('status','--porcelain')
identities={k:json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect',v],cwd=S,text=True)) for k,v in {'baseline':BASE,'origin':B['origin_source_commit'],'harness':HARNESS,'execution':git('rev-parse','HEAD')}.items()}
assert all(v['object_type']=='commit' for v in identities.values())
assert not git('diff','--name-only',BASE,B['origin_source_commit'],'--','internal','python','*.go','go.mod','go.sum','scripts')
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','GIT_'))}
env.update(GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(T/'scratch'),GOTMPDIR=str(T/'scratch'))
(T/'scratch').mkdir(exist_ok=True);os.environ.update(env)
sys.path.insert(0,str(ORIGIN/'scripts'))
from dev_guest import source_identity,verify_guest,verify_translation,CONTRACT,write
from build_generated_guest import download
origin_identity=source_identity(ORIGIN);assert origin_identity['commit']==B['origin_source_commit']
record=verify_guest(ORIGIN,T/'guest');assert record['guest_sha256']==B['guest_sha256'] and sha(T/'guest/guest.json')==B['guest_record_sha256']
expected=json.loads((T/'translation/assessment.json').read_text())
for x in expected['binding_anchors'].values():assert x['exact_match']
out=T/'install';out.mkdir()
converter=download(json.loads((ORIGIN/'release/generated-go-toolchain.json').read_text())['archives']['converter'],out/'downloads')
spike=ORIGIN/'benchmarks/spikes/generated-go-integration'
with (T/'installation.log').open('w') as log:
 for cmd in ([sys.executable,spike/'translate_guest.py','--guest',T/'guest/mariamem.wasm','--guest-sha256',B['guest_sha256'],'--converter-archive',converter,'--output',out/'translation'],[sys.executable,spike/'setup_candidate.py','--source-only','--source-module',out/'translation/module','--guest',T/'guest/mariamem.wasm','--input-manifest',out/'translation/input-manifest.json','--output',out/'candidate']):
  subprocess.run(list(map(str,cmd)),env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
verify_translation(ORIGIN,out/'translation',B['guest_sha256'])
module=out/'candidate/module';assert inventory(module)==expected['candidate_inventory']
inputs={'contract':CONTRACT,'result':'UNQUALIFIED','guest_sha256':B['guest_sha256'],'source_inventory':inventory(module),'data_sha256':sha(module/'generated/data.bin'),'candidate_files_sha256':{str(p.relative_to(module)):sha(p) for suffix in ('*.go','*.s') for p in module.rglob(suffix)},'guest_directory':str(T/'guest'),'translation_directory':str(out/'translation'),'guest_record_sha256':sha(T/'guest/guest.json'),'translation_record_sha256':sha(out/'translation/input-manifest.json')}
write(out/'installation-inputs.json',inputs)
# Only the reviewed guest identity changes in these process-local modules.
# Whole-body, table and transform checks all execute unchanged.
for name,digest in B['adapters_sha256'].items():
 path=ORIGIN/'scripts'/(name+'.py');assert sha(path)==digest
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 assert mod.GUEST_SHA256==B['canonical_guest_sha256'];mod.GUEST_SHA256=B['guest_sha256'];sys.modules[name]=mod
spec=importlib.util.spec_from_file_location('dict_experiment_installer',ORIGIN/'scripts/generate_runtime.py');installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
sys.argv=['generate_runtime.py','--source-module',str(module),'--development-input',str(out/'installation-inputs.json'),'--output',str(out/'generatedgo')]
installer.main()
product=T/'candidate';product.mkdir()
for name in origin_identity['files_sha256']:
 if name.startswith('internal/generatedgo/'):continue
 dest=product/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ORIGIN/name,dest)
shutil.move(out/'generatedgo',product/'internal/generatedgo')
kind=product/'internal/runtimekind/kind.go';text=kind.read_text();old='const GuestSHA256 = "'+B['canonical_guest_sha256']+'"';assert text.count(old)==1;kind.write_text(text.replace(old,'const GuestSHA256 = "'+B['guest_sha256']+'"'))
assert source_identity(ORIGIN)==origin_identity
assert verify_guest(ORIGIN,T/'guest')==record
assert not git('status','--porcelain')
dump(E/'installation.json',{'result':'UNQUALIFIED_INSTALLED_NOT_EXECUTED','source':identities,'guest_sha256':B['guest_sha256'],'reproduced_candidate_inventory_matches_ci':True,'adapter_changes':'only process-local GUEST_SHA256; original validators/transforms unchanged','generated_inventory_sha256':hashlib.sha256(json.dumps(inventory(product/'internal/generatedgo'),sort_keys=True).encode()).hexdigest()})
print('INSTALLATION PASS: full local translated inventory equals CI; original guards applied',flush=True)

def archive(ref,paths,dest):
 p=T/'source.tar'
 with p.open('wb') as f:subprocess.run(['git','archive',ref,*paths],cwd=S,stdout=f,check=True)
 with tarfile.open(p) as f:f.extractall(dest,filter='data')
 p.unlink()
(T/'baseline').mkdir();archive(BASE,[],T/'baseline')
inject=T/'instrument.py';inject.write_bytes(subprocess.check_output(['git','show','e556c36570e1be023f8a9c8243381c6605079592:benchmarks/uca-p8-attribution/reproduction/instrument.py'],cwd=S))
for arm in ['baseline','candidate']:
 A=T/arm;archive(HARNESS,['tests/timer_calibration/runner'],A)
 runner=A/'tests/timer_calibration/runner';unchanged=inventory(A/'internal/generatedgo')
 for mode in ['off','phases']:
  if mode=='phases':subprocess.run([sys.executable,inject,S,runner],check=True,env=env)
  before=inventory(runner);binary=T/(arm+'-'+mode+'.test');start=time.monotonic()
  with (T/(arm+'-'+mode+'-build.log')).open('w') as log:
   subprocess.run(['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-c','-o',binary,'./maria/store'],cwd=runner,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
  assert unchanged==inventory(A/'internal/generatedgo')
  dump(E/(arm+'-'+mode+'-runner.json'),{'source':identities['baseline' if arm=='baseline' else 'origin'],'execution_source':identities['execution'],'harness':identities['harness'],'harness_files_sha256':before,'binary_sha256':sha(binary),'compile_seconds':time.monotonic()-start,'guest_sha256':B['canonical_guest_sha256'] if arm=='baseline' else B['guest_sha256'],'buildinfo':subprocess.check_output(['go','version','-m',binary],env=env,text=True).replace(str(T),'<TEMP>')})
  print(arm,mode,'BUILD PASS',round(time.monotonic()-start,1),flush=True)
for mode in ['off','phases']:
 assert json.loads((E/('baseline-'+mode+'-runner.json')).read_text())['harness_files_sha256']==json.loads((E/('candidate-'+mode+'-runner.json')).read_text())['harness_files_sha256']
print('FOUR RUNNERS READY; measurement not started',flush=True)
