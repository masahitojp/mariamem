#!/usr/bin/env python3
"""Static name/owner audit of the tiny linked module, not runtime reachability."""
import argparse
import hashlib
import json
from pathlib import Path
import re
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();repo=Path(__file__).resolve().parents[3];e=w/'evidence';text=(w/'temp/primitives.wat').read_text()
base=(repo/'internal/generatedgo/code/base/base.go').read_text();host=(repo/'internal/generatedgo/main.go').read_text()
imports=[]
for line in text.splitlines():
 match=re.match(r' \(import "([^"]+)" "([^"]+)" (.*)',line)
 if not match:continue
 module,name,declaration=match.groups();method=name[:1].upper()+name[1:]
 row={'module':module,'name':name,'declaration':declaration}
 if module=='env' and name=='memory':row.update(owner='generated base.Module/shared memory constructor',classification='special existing shared-memory facility')
 elif module=='wasi' and name=='thread-spawn':row.update(owner='internal/generatedgo/code/base/base.go ThreadSpawn',classification='special existing thread-spawn facility')
 elif module=='wasix_32v1':
  assert re.search(r'\b'+method+r'\(',base),method
  found=re.search(r'func \(h \*host\) '+method+r'\([^\n]+',host);assert found,method
  row.update(owner='internal/generatedgo/main.go '+method,definition=found[0],classification='existing fail-closed panic' if name in ['thread_signal','proc_exit2'] else 'existing handwritten host method')
 elif module=='wasi_snapshot_preview1':
  assert re.search(r'func \(w \*WasiStubs\) '+method+r'\(',base),method
  row.update(owner='internal/generatedgo/code/base/base.go WasiStubs.'+method,classification='existing WASI method; semantic limits need runtime tests')
 else:raise AssertionError((module,name))
 imports.append(row)
start=re.search(r'^ \(func \$probe_callback ',text,re.M).start();end=text.index('\n (func ',start+1);callback=text[start:end];assert 'call_indirect' in callback
(e/'callback.wat').write_text(callback+'\n')
exports=re.findall(r'^ \(export "([^"]+)"',text,re.M)
for name in ['probe_callback','wasi_thread_start','__wasm_init_tls','_start']:assert name in exports,name
files=[repo/'guest/experimental.patch',repo/'guest/input.json',repo/'guest/source.patch',repo/'release/generated-go-toolchain.json',repo/'internal/generatedgo/main.go',repo/'internal/generatedgo/runtime_instance.go',repo/'internal/generatedgo/code/base/base.go',repo/'internal/generatedgo/code/base/runtime_failure.go',repo/'internal/guest/linked.go',repo/'scripts/build_generated_guest.py',repo/'scripts/prepare_guest.py',repo/'scripts/dev_guest.py']
files+=sorted(Path(__file__).parent.glob('*.py'))+sorted(Path(__file__).parent.glob('*.cc'))+sorted(Path(__file__).parent.glob('*.sh'))
result={'scope':'static small-module compile/link only; no execution or whole-engine import inventory','imports':imports,'unknown_import_names':[],'fail_closed_imports':[x['name'] for x in imports if 'fail-closed' in x['classification']],'exports':exports,'callback_indirect_preserved':True,'wasm_sha256':hashlib.sha256((w/'temp/primitives.wasm').read_bytes()).hexdigest(),'wasm_bytes':(w/'temp/primitives.wasm').stat().st_size,'validated_copy_sha256':hashlib.sha256((w/'temp/validated.wasm').read_bytes()).hexdigest(),'source_hashes':{str(x.relative_to(repo)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}}
(e/'primitives.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'imports':len(imports),'unknown_import_names':[],'fail_closed_imports':result['fail_closed_imports'],'callback_indirect_preserved':True},indent=2))
