#!/usr/bin/env python3
"""Generate product-baseline experiment delta with a WASIX C++ entry."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();repo=Path(__file__).resolve().parents[3];sp=Path(__file__).parent
product=w/'temp/product';prior=repo/'benchmarks/spikes/issue65-wasix-preflight/evidence/composed-draft.patch'
expected='81956fc2961143914965c5202c50695d1532c264745940fbf05d5a9537d3385a'
assert json.loads((w/'evidence/overlay.json').read_text())['patches']['guest/experimental.patch']==expected
base=prior.read_text();mark='--- /dev/null\n+++ b/libmysqld/mariamem_wire_probe.inc\n';start=base.index(mark);end=base.index('\n--- ',start+len(mark))
entry=(repo/'benchmarks/spikes/issue65-native-control/session.inc').read_text()
base=base[:start]+''.join(difflib.unified_diff([],entry.splitlines(True),fromfile='/dev/null',tofile='b/libmysqld/mariamem_wire_probe.inc')).rstrip('\n')+base[end:]
patch=[base];pins={}
def add(name,new):
 old=(product/name).read_text() if (product/name).exists() else ''
 assert old!=new,name
 patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name if old else '/dev/null',tofile='b/'+name))
 pins[name]={'product_sha256':hashlib.sha256(old.encode()).hexdigest() if old else None,'after_sha256':hashlib.sha256(new.encode()).hexdigest()}
name='wasm/CMakeLists.txt';s=(product/name).read_text();anchor='  ADD_EXECUTABLE(lite4mariadb-wasix lite4mariadb.c)';assert s.count(anchor)==1
s=s.replace(anchor,anchor[:-1]+' issue65_control.cc)\n  SET_SOURCE_FILES_PROPERTIES(lite4mariadb.c PROPERTIES COMPILE_DEFINITIONS "main=issue65_legacy_main")\n  TARGET_COMPILE_FEATURES(lite4mariadb-wasix PRIVATE cxx_std_17)')
add(name,s)
name='cmake/os/WASIX.cmake';add(name,(product/name).read_text()+'\n# Experimental coherent embedded/native protocol build, all translation units.\nADD_COMPILE_DEFINITIONS(MARIAMEM_NATIVE_WIRE)\n')
name='wasm/lite4mariadb.c';add(name,(product/name).read_text()+'\n'+(sp/'bootstrap.inc').read_text())
add('wasm/issue65_control.cc',(sp/'control.cc').read_text())
(repo/'guest/experimental.patch').write_text(''.join(patch))
(w/'evidence/entry-source.json').write_text(json.dumps({'prior_composed_patch_sha256':hashlib.sha256(prior.read_bytes()).hexdigest(),'entry_files':pins,'experimental_patch_sha256':hashlib.sha256((repo/'guest/experimental.patch').read_bytes()).hexdigest()},indent=2)+'\n')
print('Generated complete product-baseline experimental patch plus WASIX entry')
