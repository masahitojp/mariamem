"""Derive this trial's exact inputs from the inspected complete old target tree.
Run before builds; committed full-image pins are mandatory on every producer.
"""
import difflib,hashlib,json,re,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent/'inputs'
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(p.read_text())
pin=load(R/'guest/input.json');old=load(OUT/'legacy-prepared.json')
names=[i['file'] for i in old['files']];final={n:(R/'build/source'/n).read_bytes() for n in names}
# Preparation adds independently pinned initialization diagnostics after overlays.
# Remove only these exact known insertions before reconstructing overlay inputs.
n='libmysqld/lib_sql.cc';b=final[n];header=b'#include "mariamem_init_diagnostics.h"\n';assert b.startswith(header);b=b[len(header):]
for event in ('embedded_begin','embedded_options_complete','embedded_complete'):
 mark=('  mariamem_init_mark("'+event+'");\n').encode();assert b.count(mark)==1;b=b.replace(mark,b'')
final[n]=b
base=R/'build/experiment-work/issue137/temp/profile-baseline';base.mkdir(exist_ok=False)
for n,b in final.items():
 expected=pin['native_overlay']['after_sha256'].get(n,next(i['after_sha256'] for i in old['files'] if i['file']==n));assert sha(b)==expected,(n,sha(b),expected)
sections=re.split(rb'(?=^--- )',(R/'guest/experimental.patch').read_bytes(),flags=re.M)
def target(s):
 m=re.search(rb'^\+\+\+ b/(.+)$',s,re.M);return m[1].decode() if m else ''
# Recover pristine full files from the already hash-verified source archive.
# The old patch contains zero-context insertions; do not guess reverse positions.
import tarfile
with tarfile.open(R/'build/downloads/mariadb-13.0.2-source.tar.gz') as archive:
 for n in names:
  matches=[m for m in archive.getmembers() if m.name.endswith('/'+n)];assert len(matches)==1
  p=base/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.extractfile(matches[0]).read())
for section in re.split(rb'(?=^--- )',(R/'guest/patches/common-portability.patch').read_bytes(),flags=re.M):
 if target(section)=='libmysqld/libmysql.c':subprocess.run(['patch','--batch','--fuzz=0','-p1'],cwd=base,input=section,check=True)
before={n:(base/n).read_bytes() for n in names}
for i in old['files']:assert sha(before[i['file']])==i['before_sha256']
prepared=dict(before)
prepared[names[0]]=before[names[0]].replace(b'set_time(&tm, MYSQL_TIMESTAMP_TIME, MAX_TIME_WIDTH);',b'set_time(&tm, MYSQL_TIMESTAMP_TIME, MAX_TIME_FULL_WIDTH);',1)
guard=b'#ifdef __wasi__\n  /* Metadata allocation failure must be returned before strlen dereferences. */\n  if (!client_field->db || !client_field->table || !client_field->name ||\n      !client_field->org_table || !client_field->org_name)\n    return true;\n#endif\n\n'
assert final[names[2]].count(guard)==1
anchor=b'  client_field->db_length=\t\t(uint)strlen(client_field->db);';assert before[names[2]].count(anchor)==1
prepared[names[2]]=before[names[2]].replace(anchor,guard+anchor)
newfinal=dict(final)
attr=b'#ifdef __wasi__\n    /* Type attributes belong to the descriptor, including NULL values.\n       Match set_conversion_functions before selecting the type handler. */\n    param->unsigned_flag= client_param->is_unsigned;\n#endif\n';assert newfinal[names[0]].count(attr)==2
newfinal[names[0]]=newfinal[names[0]].replace(attr,b'')
a=newfinal[names[0]].index(b'\n#if defined(EMBEDDED_LIBRARY) && defined(__wasi__)\n/* Public C API adapter');b=newfinal[names[0]].index(b'unsigned long mariamem_spike_decodes= 0;',a)
newfinal[names[0]]=newfinal[names[0]][:a]+b'\n'+newfinal[names[0]][b:]
a=newfinal[names[2]].index(b'\n#ifdef __wasi__\nextern "C" void *mariamem_stmt_parameter_items');b=newfinal[names[2]].index(b'#include "mariamem_wire_probe.inc"',a)
newfinal[names[2]]=newfinal[names[2]][:a]+b'\n'+newfinal[names[2]][b:]
newfinal[names[1]]=before[names[1]]
def diff(n,a,b):return ''.join(difflib.unified_diff(a.decode().splitlines(True),b.decode().splitlines(True),fromfile='a/'+n,tofile='b/'+n)).encode()
patch=b''.join(diff(n,before[n],prepared[n]) for n in names);path=R/'guest/patches/13.0.2-native-prepared.patch';path.write_bytes(patch)
entry={'file':str(path.relative_to(R)),'sha256':sha(patch),'before_sha256':{n:sha(before[n]) for n in names if before[n]!=prepared[n]},'after_sha256':{n:sha(prepared[n]) for n in names if before[n]!=prepared[n]}}
np=dict(old,profile='native-text',patch_file=entry['file'],patch_sha256=entry['sha256'],files=[dict(file=n,before_sha256=sha(before[n]),after_sha256=sha(prepared[n])) for n in names],unchanged_files={names[1]:sha(before[names[1]])},purpose='Trial native TIME and embedded text metadata allocation guard; no legacy MYSQL_BIND or parameter metadata adapter repairs')
(R/'guest/prepared_source_patch.json').write_text(json.dumps(np,indent=2)+'\n');(OUT/'native-prepared.json').write_text(json.dumps(np,indent=2)+'\n')
pin['patches']=[entry if e['file']==old['patch_file'] else e for e in pin['patches']];pin['prepared_profile']='native-text'
# Collapse only the affected native patch sections to exact profile pre/postimages.
seen=set();result=b''
for s in sections:
 n=target(s)
 if n in names:
  if n not in seen:result+=diff(n,prepared[n],newfinal[n]);seen.add(n)
 else:result+=s
(R/'guest/experimental.patch').write_bytes(result)
no=pin['native_overlay'];no['sha256']=sha(result)
for n in names:
 if n in no['before_sha256']:no['before_sha256'][n]=sha(prepared[n]);no['after_sha256'][n]=sha(newfinal[n])
(R/'guest/input.json').write_text(json.dumps(pin,indent=2)+'\n')
(OUT/'source-review.json').write_text(json.dumps({'old_full':{n:sha(b) for n,b in final.items()},'before':{n:sha(b) for n,b in before.items()},'native_prepared':{n:sha(b) for n,b in prepared.items()},'native_final':{n:sha(b) for n,b in newfinal.items()},'removed_exports':['mariamem_stmt_parameter_items','mariamem_stmt_parameter_metadata'],'retained':'TIME full width; embedded text metadata OOM guard; native conversion snapshot and all native controller logic'},indent=2)+'\n')
print('Derived exact native profile; legacy patch unchanged')
