import argparse,json,os,shutil,sys,time
from pathlib import Path
owner=Path.cwd();w=owner/'build/issue128-real/temp/runtime/legacy';repo=w/'worktree';sys.path.insert(0,str(repo/'scripts'))
from common import digest
from dev_guest import verify_guest,verify_translation,inventory,source_identity,write,CONTRACT
from build_feedback import go_environment,run
p=argparse.ArgumentParser();p.add_argument('stage',choices=['translate','compile','test']);a=p.parse_args()
artifact=owner/'build/issue128-real/temp/legacy/output/artifact'
record=verify_guest(repo,artifact);assert record['fresh_canonical_builder_success'] is True and record['fresh_target_producer_success'] is True
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w)
(w/'temp/go-tmp').mkdir(exist_ok=True)
env=go_environment(dict({k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')},TMPDIR=str(w/'temp/go-tmp'),GOTMPDIR=str(w/'temp/go-tmp'),CGO_ENABLED='0',GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',GOGC='50',MARIAMEM_PHASE_TRACE=str(w/'evidence/host-phases.jsonl')))
out=w/'temp/host';spike=repo/'benchmarks/spikes/generated-go-integration';origin=source_identity(repo)
if a.stage=='translate':
 out.mkdir();write(w/'evidence/host-deadline.json',{'started_unix':time.time(),'deadline_unix':time.time()+1800})
 converter=owner/'build/issue128-real/temp/downloads/wasm2go-upstream.tar.gz'
 run([sys.executable,str(spike/'translate_guest.py'),'--guest',str(artifact/'mariamem.wasm'),'--guest-sha256',record['guest_sha256'],'--converter-archive',str(converter),'--output',str(out/'translation')],env=env,check=True,phase='legacy:translation')
 raw=verify_translation(repo,out/'translation',record['guest_sha256'])
 run([sys.executable,str(spike/'setup_candidate.py'),'--source-only','--source-module',str(out/'translation/module'),'--guest',str(artifact/'mariamem.wasm'),'--input-manifest',str(out/'translation/input-manifest.json'),'--output',str(out/'candidate')],env=env,check=True,phase='legacy:source-adapter')
 module=out/'candidate/module'
 write(out/'installation-inputs.json',{'contract':CONTRACT,'result':'UNQUALIFIED','guest_sha256':record['guest_sha256'],'source_inventory':inventory(module),'data_sha256':digest(module/'generated/data.bin'),'candidate_files_sha256':{f.relative_to(module).as_posix():digest(f) for suffix in ('*.go','*.s') for f in module.rglob(suffix)},'guest_directory':str(artifact),'translation_directory':str(out/'translation'),'guest_record_sha256':digest(artifact/'guest.json'),'translation_record_sha256':digest(out/'translation/input-manifest.json')})
elif a.stage=='compile':
 deadline=json.loads((w/'evidence/host-deadline.json').read_text())['deadline_unix'];assert time.time()<deadline,'translation/host budget exhausted'
 module=out/'candidate/module';product=out/'product'
 for name in origin['files_sha256']:
  if name.startswith('internal/generatedgo/'):continue
  target=product/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
 runtime=out/'generatedgo'
 run([sys.executable,str(repo/'scripts/generate_runtime.py'),'--source-module',str(module),'--development-input',str(out/'installation-inputs.json'),'--development-thread-binding',str(w/'evidence/reviewed-binding/identity.json'),'--output',str(runtime)],env=env,check=True,phase='legacy:installation')
 shutil.move(str(runtime),product/'internal/generatedgo')
 kind=product/'internal/runtimekind/kind.go';old=json.loads((repo/'release/generated-go-inputs.json').read_text())['guest_sha256'];text=kind.read_text();assert text.count('const GuestSHA256 = "'+old+'"')==1;kind.write_text(text.replace(old,record['guest_sha256']))
 before=inventory(product);binary=out/'mariamem-dev-host'
 run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/mariamem-host'],cwd=product,env=env,check=True,timeout=max(1,deadline-time.time()),phase='legacy:host-compile')
 assert inventory(product)==before and source_identity(repo)==origin
 write(w/'evidence/host-build.json',{'source_commit':origin['commit'],'guest_sha256':record['guest_sha256'],'binary_sha256':digest(binary),'source_inventory':before,'binding_sha256':digest(w/'evidence/reviewed-binding/identity.json'),'completed_unix':time.time()})
else:
 product=out/'product';binary=out/'mariamem-dev-host';before=inventory(product)
 smoke_env=dict(env,PYTHONPATH=str(product/'python'),MARIAMEM_TEST_HOST=str(binary))
 run([sys.executable,'-m','pytest',str(repo/'tests/test_dev_guest_smoke.py'),'-q','--junitxml='+str(w/'evidence/dev-smoke.xml')],cwd=product,env=smoke_env,check=True,timeout=1800,phase='legacy:finite-semantic-smoke')
 import xml.etree.ElementTree as ET
 suites=list(ET.parse(w/'evidence/dev-smoke.xml').getroot().iter('testsuite'));assert sum(int(v.get('tests','0')) for v in suites)==1
 assert all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
 for name in ('v06_prepared_p1_probe.py','v06_prepared_p2_repair_probe.py'):
  run([sys.executable,str(w/'temp/tools'/name),'--host',str(binary),'--output',str(w/'evidence'/(name+'.json'))],cwd=product,env=smoke_env,check=True,timeout=900,phase='legacy:'+name)

 assert inventory(product)==before and source_identity(repo)==origin
 write(w/'evidence/semantic-result.json',{'result':'PASS original dev smoke plus original P1 and P2 repair probes','guest_sha256':record['guest_sha256'],'source_commit':origin['commit'],'scope':'Fresh SQL, InnoDB writes, commit/rollback, Snapshot, three independent Forks, shared host/close/drain checks; not native suites or public C3'})
print(a.stage,'completed')

if a.stage=='test':
 run([sys.executable,str(repo/'benchmarks/spikes/issue138-paired-capture/legacy_checkpoint.py')],cwd=product,env=smoke_env,check=True,timeout=300,phase='legacy:paired-archive')

if a.stage=='test':
 run([sys.executable,str(owner/'benchmarks/spikes/issue137-helper-continuation/legacy_spare_archive.py')],cwd=product,env=smoke_env,check=True,timeout=300,phase='legacy:positive-spare-archive')
