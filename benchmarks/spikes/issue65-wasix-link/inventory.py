"""Retain static Binaryen declarations from a linked guest; no reachability claim."""
from pathlib import Path
import hashlib,json,re,sys
w=Path(sys.argv[1]);wat=w/'temp/module.wat';out=w/'evidence';imports=[];exports=[];memory=[];tls=[];tags=[];globals_by_name={};counts={'functions':0,'data_segments':0,'mutable_globals':0}
for line in wat.open():
 if line.startswith(' (import '):imports.append(line.strip())
 elif line.startswith(' (export '):exports.append(line.strip())
 elif line.startswith(' (memory '):memory.append(line.strip())
 elif line.startswith(' (tag '):tags.append(line.strip())
 if line.startswith(' (global '):globals_by_name[line.split()[1]]=line.strip()
 if line.startswith(' (func '):counts['functions']+=1
 if line.startswith(' (data '):counts['data_segments']+=1
 if line.startswith(' (global ') and '(mut ' in line:counts['mutable_globals']+=1
base=(w/'worktree/internal/generatedgo/code/base/base.go').read_text();host=(w/'worktree/internal/generatedgo/main.go').read_text();rows=[]
for declaration in imports:
 match=re.match(r'\(import "([^"]+)" "([^"]+)"',declaration);assert match,declaration
 module,name=match.groups();method=name[:1].upper()+name[1:]
 if module=='env' and name=='memory':status='existing shared memory'
 elif module=='wasi' and name=='thread-spawn':status='existing ThreadSpawn'
 elif module=='wasix_32v1' and re.search(r'func \(h \*host\) '+method+r'\(',host):status='existing fail-closed method' if f'panic("unimplemented WASIX: {method}")' in host else 'existing handwritten host method'
 elif module=='wasi_snapshot_preview1' and re.search(r'func \(w \*WasiStubs\) '+method+r'\(',base):status='existing WASI method'
 else:status='not found in current host; assess before execution'
 rows.append({'module':module,'name':name,'declaration':declaration,'host_name_status':status})
for line in exports:
 if any('\"'+name+'\"' in line for name in ['__tls_base','__tls_size','__tls_align']):
  symbol=re.search(r'\(global ([^ )]+)\)',line)[1];tls.append({'export':line,'global':globals_by_name[symbol]})
wasm=w/'temp/artifact/mariamem.wasm';result={'scope':'actual linked/postoptimized module static declarations only; no runtime execution or import reachability acceptance','guest_sha256':hashlib.sha256(wasm.read_bytes()).hexdigest(),'guest_bytes':wasm.stat().st_size,'imports':rows,'exports':exports,'defined_memory':memory,'TLS_globals':tls,'tags':tags,'counts':counts,'unknown_import_names':[x for x in rows if x['host_name_status'].startswith('not found')],'declared_fail_closed_imports':[x['name'] for x in rows if x['host_name_status']=='existing fail-closed method']}
assert any('"_start"' in x for x in exports)
assert any('"wasi_thread_start"' in x for x in exports)
assert any('"__wasm_init_tls"' in x for x in exports)
assert len(tls)==3
(out/'module-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['guest_sha256','guest_bytes','counts','unknown_import_names','declared_fail_closed_imports']},indent=2))
