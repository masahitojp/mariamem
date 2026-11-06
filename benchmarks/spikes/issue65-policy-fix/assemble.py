#!/usr/bin/env python3
"""Isolated UNQUALIFIED wire-host assembly using existing checked stages."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--translate-only',action='store_true');a=p.parse_args();w=a.workspace.resolve();repo=w/'worktree';sys.path.insert(0,str(repo/'scripts'))
from dev_guest import verify_guest,verify_translation,inventory,source_identity,write,CONTRACT,install_inputs
from build_feedback import go_environment,run
from common import digest
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w)
isolated_env={k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')}
env=go_environment(dict(isolated_env,CGO_ENABLED='0',GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',GOGC='50',MARIAMEM_PHASE_TRACE=str(w/'evidence/host-phases.jsonl')))
guest=w/'temp/artifact';record=verify_guest(repo,guest);origin=source_identity(repo);out=w/'temp/host';out.mkdir(exist_ok=a.resume)
spike=repo/'benchmarks/spikes/generated-go-integration';translation=out/'translation'
if not a.resume:
 run([sys.executable,str(spike/'translate_guest.py'),'--guest',str(guest/'mariamem.wasm'),'--guest-sha256',record['guest_sha256'],'--converter-archive',str(repo/'build/downloads/wasm2go-upstream.tar.gz'),'--output',str(translation)],env=env,check=True,phase='wire:translation')
raw=verify_translation(repo,translation,record['guest_sha256'])
if not a.resume:
 run([sys.executable,str(spike/'setup_candidate.py'),'--source-only','--source-module',str(translation/'module'),'--guest',str(guest/'mariamem.wasm'),'--input-manifest',str(translation/'input-manifest.json'),'--output',str(out/'candidate')],env=env,check=True,phase='wire:source-adapter')
module=out/'candidate/module'
if a.resume:install_inputs(json.loads((out/'installation-inputs.json').read_text()),module,root=repo)
inputs={'contract':CONTRACT,'result':'UNQUALIFIED','guest_sha256':record['guest_sha256'],'source_inventory':inventory(module),'data_sha256':digest(module/'generated/data.bin'),'candidate_files_sha256':{p.relative_to(module).as_posix():digest(p) for suffix in ('*.go','*.s') for p in module.rglob(suffix)},'guest_directory':str(guest),'translation_directory':str(translation),'guest_record_sha256':digest(guest/'guest.json'),'translation_record_sha256':digest(translation/'input-manifest.json')}
write(out/'installation-inputs.json',inputs)
if a.translate_only:
 print('Verified translation/candidate ready for exact binding review',flush=True);raise SystemExit(0)
assembler_pin=digest(Path(__file__));template_pins={p.name:digest(p) for p in (w/'temp/tools').glob('*.txt')}
product=out/'product'
for name in origin['files_sha256']:
 if name.startswith('internal/generatedgo/'):continue
 target=product/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
runtime=product/'internal/generatedgo';staged_runtime=out/'generatedgo'
run([sys.executable,str(repo/'scripts/generate_runtime.py'),'--source-module',str(module),'--development-input',str(out/'installation-inputs.json'),'--development-thread-binding',str(w/'temp/tools/binding.json'),'--output',str(staged_runtime)],env=env,check=True,phase='wire:installation')
kind=product/'internal/runtimekind/kind.go'
old=json.loads((repo/'release/generated-go-inputs.json').read_text())['guest_sha256'];kind_text=kind.read_text();assert kind_text.count('const GuestSHA256 = "'+old+'"')==1
kind.write_text(kind_text.replace('const GuestSHA256 = "'+old+'"','const GuestSHA256 = "'+record['guest_sha256']+'"'))
shutil.move(str(staged_runtime),runtime)
# Experimental host additions after the checked installer, inventoried separately.
shutil.copyfile(w/'temp/tools/runtime_wire.go.txt',runtime/'runtime_wire.go')
# Isolated host overlays are explicit inputs, never substituted into guest origin.
for name in ('endpoint.go','endpoint_test.go'):
 shutil.copyfile(w/'temp/tools'/(name+'.txt'),product/'internal/live'/name)
cmd=product/'cmd/issue65-wire';cmd.mkdir();shutil.copyfile(w/'temp/tools/main.go.txt',cmd/'main.go');shutil.copyfile(w/'temp/tools/wire_test.go.txt',cmd/'wire_test.go');shutil.copyfile(w/'temp/tools/capture_test.go.txt',cmd/'capture_test.go');shutil.copyfile(w/'temp/tools/runtime_capture_test.go.txt',runtime/'runtime_capture_test.go')
for name in ('live.go','live_test.go','compat_test.go','fix_controls_test.go','limits_test.go','policy_controls_test.go'):
 shutil.copyfile(w/'temp/tools'/(name+'.txt'),cmd/name)
go_root=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip());run([str(go_root/'bin/gofmt'),'-w',str(runtime/'runtime_wire.go'),str(cmd/'main.go'),str(cmd/'wire_test.go'),str(cmd/'capture_test.go'),str(runtime/'runtime_capture_test.go'),str(cmd/'live.go'),str(cmd/'live_test.go'),str(cmd/'compat_test.go'),str(cmd/'fix_controls_test.go'),str(cmd/'limits_test.go'),str(cmd/'policy_controls_test.go')],env=env,check=True,phase='wire:gofmt')
pins=inventory(product);binary=out/'wire.test'
run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/issue65-wire'],cwd=product,env=env,check=True,phase='wire:host-compile')
assert inventory(product)==pins;assert source_identity(repo)==origin
assert digest(Path(__file__))==assembler_pin;assert {p.name:digest(p) for p in (w/'temp/tools').glob('*.txt')}==template_pins
write(w/'evidence/host-build.json',{'contract':'issue65-wire-prototype-unqualified','guest_sha256':record['guest_sha256'],'guest_source_commit':record['source_commit'],'host_source_commit':origin['commit'],'tooling_source_commit':os.environ['MARIAMEM_TOOLING_SOURCE_COMMIT'],'source_inventory':pins,'assembler_sha256':assembler_pin,'runtime_adapter_origin_sha256':digest(repo/'internal/generatedgo/runtime_instance.go'),'prototype_templates_sha256':template_pins,'binding_sha256':digest(w/'temp/tools/binding.json'),'binary_sha256':digest(binary),'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True),'translation_record_sha256':digest(translation/'input-manifest.json'),'installation_inputs_sha256':digest(out/'installation-inputs.json')})
print('Built isolated wire test binary:',binary,flush=True)
