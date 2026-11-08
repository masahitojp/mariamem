#!/usr/bin/env python3
"""Finish the same development build after restoring a required public header.

This is an explicitly recorded incremental continuation, never Release evidence
or a successful fresh invocation of build_generated_guest.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from common import digest
from dev_guest import source_identity, CONTRACT
from git_identity import require_commit
from install_guest_toolchain import inventory

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-commit', required=True)
a = p.parse_args()
require_commit(ROOT, a.source_commit)
identity = source_identity(ROOT)
assert identity['commit'] == a.source_commit
out = Path('/output/artifact')
assert out.is_dir() and not any(out.iterdir()), 'require empty failed-producer output'
sdk = Path('/root/.wasixcc')
work = Path('/work/source')
assert (work/'build-legacy-no-postopt').is_dir()
pins = json.loads((ROOT/'release/generated-go-toolchain.json').read_text())
archives = {k: ROOT/'build/downloads'/v['file'] for k, v in pins['archives'].items()}
for key, path in archives.items():
    assert digest(path) == pins['archives'][key]['sha256'], key

env = {k:v for k,v in os.environ.items() if not k.startswith('WASIXCC_')}
env.update(PATH=str(sdk/'bin')+':/usr/bin:/bin', LD_LIBRARY_PATH=str(sdk/'llvm/lib'),
           LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH='0')
subprocess.run([sys.executable, ROOT/'scripts/prepare_guest.py'], env=env, check=True)
fresh = ROOT/'build/source'
subprocess.run([sys.executable, Path(__file__).with_name('check_source.py'),
                '--source', fresh, '--output', '/output/prepared-check-corrected.json'], check=True)
old_controller = work/'wasm/issue65_control.cc'
assert digest(old_controller) == 'b9de8206b5d359ee25daa3aa2b138d0242cbec1b0e76d27fd95795d565cb4e1f'
shutil.copy2(fresh/'wasm/issue65_control.cc', old_controller)
# Compare every prepared source file, not only the 61 overlay manifest entries.
prepared_files = {}
for file in sorted(fresh.rglob('*')):
    if file.is_file():
        name = file.relative_to(fresh).as_posix()
        value = digest(file)
        assert value == digest(work/name), 'compiled-tree source differs: '+name
        prepared_files[name] = value
(Path('/output/source-files.json')).write_text(json.dumps(prepared_files,indent=2)+'\n')
objects = work/'build-legacy-no-postopt'
old_objects = {str(f.relative_to(work)):digest(f) for f in sorted(objects.rglob('*.o'))
               if f.name != 'issue65_control.cc.o'}
shell = ROOT/'benchmarks/spikes/wasm2go/legacy_eh_toolchain.sh'
subprocess.run(['bash', shell, 'build-no-postopt'], env=env, check=True)
assert all(digest(work/name) == value for name,value in old_objects.items()), 'engine objects changed'
subprocess.run(['bash', shell, 'postopt'], env=env, check=True)
linked = Path('/work/artifact/mariamem-legacy-eh.wasm')
guest = Path('/work/artifact/mariamem-legacy-eh-O2-compatible.wasm')
shutil.copy2(linked, out/'linked.wasm')
shutil.copy2(guest, out/'mariamem.wasm')
for name in ('link.txt','flags.make','CMakeCache.txt'):
    shutil.copy2(Path('/work/artifact')/name,out/name)
versions = {}
for key, command in [('wasixcc',[sdk/'bin/wasixccenv','--version']),
                     ('llvm',[sdk/'llvm/bin/clang','--version']),
                     ('lld',[sdk/'llvm/bin/wasm-ld','--version']),
                     ('binaryen',[sdk/'binaryen/bin/wasm-opt','--version']),
                     ('cmake',['cmake','--version']),('bison',['bison','--version']),
                     ('make',['make','--version']),('python',[sys.executable,'--version'])]:
    versions[key] = subprocess.check_output(command,env=env,text=True).strip()
record = {'contract':CONTRACT,'result':'UNQUALIFIED','source_commit':a.source_commit,
          'source_identity':identity,'guest_sha256':digest(guest),'guest_bytes':guest.stat().st_size,
          'repetitions':[{'linked_sha256':digest(linked),'guest_sha256':digest(guest)}],
          'prepared_source':json.loads((ROOT/'build/prepared-source.json').read_text()),
          'toolchain':{'contract':'generated-go-v1','pins_sha256':digest(ROOT/'release/generated-go-toolchain.json'),
                       'host':'linux-arm64','versions':versions,'sysroot':inventory(sdk/'sysroot'),
                       'archives_sha256':{k:digest(v) for k,v in archives.items()},
                       'environment':{k:env[k] for k in ('PATH','LD_LIBRARY_PATH','LC_ALL','TZ','SOURCE_DATE_EPOCH')}},
          'canonical_build_sha256':digest(ROOT/'release/generated-go-build.json'),
          'build_method':'incremental continuation of failed dd33d84e fresh development build',
          'fresh_canonical_builder_success':False,
          'compared_prepared_source_files':len(prepared_files),
          'source_files_record_sha256':digest(Path('/output/source-files.json')),
          'unchanged_preexisting_objects':len(old_objects)}
assert source_identity(ROOT) == identity
(out/'guest.json').write_text(json.dumps(record,indent=2)+'\n')
base=objects/'wasm/CMakeFiles/lite4mariadb-wasix.dir'
deps={n:(base/(n+'.o.d')).read_text() for n in ('lite4mariadb.c','issue65_control.cc')}
assert 'mysql.h' in deps['issue65_control.cc']
assert all(n not in deps['lite4mariadb.c'] for n in ('resident.inc','prepared_api.inc','wire_api.inc','snapshot_fs.inc'))
Path('/output/dependencies-corrected.json').write_text(json.dumps({'result':'PASS actual compiler includes','dependencies':deps},indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('source_commit','guest_sha256','guest_bytes','compared_prepared_source_files','unchanged_preexisting_objects','build_method')},indent=2))
