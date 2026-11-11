import hashlib,json,re,subprocess
from pathlib import Path
R='1c5a6d59c70f6b5e39e1e92d0f659cb3f83b59b1'
out=Path('docs/design/issue65-native-protocol/evidence/issue131-maintenance-map.json')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
classes={
'include/violite.h':[1], 'sql-common/client.c':[1], 'libmysqld/lib_sql.cc':[1,2],
'libmysqld/mariamem_control_abi.h':[2], 'libmysqld/mariamem_wire_probe.inc':[1,2],
'sql/item.h':[1,2], 'sql/net_serv.cc':[1], 'sql/protocol.cc':[1], 'sql/protocol.h':[1],
'sql/sql_acl.cc':[1,2,3], 'sql/sql_class.cc':[1], 'sql/sql_class.h':[1],
'sql/sql_parse.cc':[1,2], 'sql/sql_prepare.cc':[1,2,4], 'wasm/CMakeLists.txt':[1,2,4],
'cmake/os/WASIX.cmake':[1], 'wasm/lite4mariadb.c':[1,2,4],
'wasm/issue65_control.cc':[1,2,3,4], 'sql/mariamem_wire_policy.h':[1,2,3], 'wasm/issue65_deadline.h':[2,3]}
notes={
'CMakeLists.txt':'Shared cross-build target selection; retain WASIX embedded entry and disable host-only targets; exact stages/fresh build detect drift.',
'cmake/os/Emscripten.cmake':'Build profile definition; Emscripten is not the measured WASIX execution route; do not infer runtime need or remove another supported profile.',
'cmake/os/WASIX.cmake':'Shared WASIX compiler/plugin/syscall profile plus native-specific define; independently owned configuration still needs upstream CMake review.',
'cmake/pcre.cmake':'Shared dependency toolchain forwarding and vendored source; recheck upstream CMake URL/API and exact pins.',
'configure.cmake':'Shared cross-compile syscall feature overrides; compiler probes may otherwise falsely enable unavailable features.',
'include/my_global.h':'Shared missing lock constants/dladdr guards; retain disabled locking semantics and header compatibility.',
'include/my_stacktrace.h':'Shared unsupported WASIX crash-resolver fork guard; diagnostic path is not normal SQL execution.',
'libmysqld/libmysql.c':'Shared getlogin portability; bootstrap mysql_real_connect remains reachable even when prepared C API excluded.',
'mysys/CMakeLists.txt':'Shared portable CRC selection, not native protocol work.',
'mysys/my_largepage.c':'Shared committed/aligned allocation and zero-fill/free lifecycle; allocator checks and exact source pins.',
'mysys/my_lock.c':'Shared unsupported filesystem locking guard; private-process FS contract retained.',
'storage/innobase/fil/fil0fil.cc':'Shared WASIX portability; file lifecycle must be checked against exact patch hunk and storage runtime, not host transport tests.',
'storage/innobase/log/log0log.cc':'Shared redo protection portability; actual moved mprotect repair on13.0.2, no native-specific repair.',
'storage/maria/ma_loghandler.c':'Shared directory fsync suppression for WASIX; bootstrap/storage reaches Aria; exact source and filesystem controls.',
'include/my_sys.h':'Shared aligned allocation declaration; review ABI/free pairing with buf0buf.',
'storage/innobase/buf/buf0buf.cc':'Shared actual extent-aligned allocation; allocator contract protects it.',
'wasm/lite4mariadb.c':'Shared embedded text bootstrap plus excluded legacy bridge; routine metadata SELECT keeps embedded Protocol reachable.',
'wasm/CMakeLists.txt':'Shared entry/build/export configuration; native excludes legacy through BOOTSTRAP_ONLY; mixed macros must fail closed.',
'mysys/my_lib.c':'Shared readable directory handling for WASIX mode bits; bootstrap/database metadata path.',
'storage/innobase/buf/buf0flu.cc':'Shared sync-LSN under-lock wait recheck;13.0.2 timed_wait/create_spare_archive retained; archive branch hit/capture restore unproved.',
'include/m_ctype.h':'Shared prepared UCA declarations/header contract; numeric/layout/provenance checks.',
'strings/ctype-uca.c':'Shared prepared UCA initialization/table lookup; engine collations and numeric/header proofs.',
}
def inventory(path,native=False):
 lines=Path(path).read_text().splitlines();rows=[];row=None
 for n,line in enumerate(lines,1):
  if line.startswith('+++ b/'):
   target=line[6:]; row={'target':target,'patch_line':n-1,'hunks':[],'classes':classes[target] if native else [1], 'confidence':'source-high; removal/runtime not newly verified'}
   if not native: row['maintenance_note']=notes.get(target,'Shared portability/build contact; see exact hunk and full-file stage identities, fresh producer and affected runtime controls.')
   rows.append(row)
  elif line.startswith('@@') and row:row['hunks'].append({'patch_line':n,'header':line})
 return {'path':path,'source_commit':R,'sha256':digest(path),'sections':rows}
patches=['guest/experimental.patch','guest/patches/common-portability.patch','guest/patches/13.0.2-redo.patch','guest/patches/13.0.2-buffer-alignment.patch','guest/patches/13.0.2-prepared.patch','guest/source.patch','benchmarks/spikes/issue128-real/inputs/shared-source.patch']
reconstructed=[]
for p in sorted(Path('build/experiment-work/issue131-source/temp/source').rglob('*')):
 if not p.is_file():continue
 lines=p.read_text().splitlines(); syms=[]
 for n,line in enumerate(lines,1):
  if re.search(r'(Manager\(|(?:void|bool|int|size_t|std::string|static size_t|static int|extern "C" int)\s+\w+\s*\(|struct \w+|enum \w+)',line):syms.append({'line':n,'text':line[:line.find('{')+1] if '{' in line else line})
 reconstructed.append({'target':p.relative_to('build/experiment-work/issue131-source/temp/source').as_posix(),'sha256':digest(p),'lines':len(lines),'symbols':syms})
evidence={
'schema':1,'analysis_date':'2026-11-08','source_commit':R,'branch':'experiment/issue131-maintenance-map',
'sources':{'initial_surface':['a5ee1ed9cc2c6932d317fba77c339b364acd48df','28e962b0f25fec6c2f7787e9d0338319abdeaf60'],'native127_origin':'8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3','native1302_producer':'e6502de0781826488c984aa5637dfe593a74799d','public1233_integration':'fd7aea9178a0f798de4a742ddb573a877f6c1f28','engine_source_commit':'620a4b5624222048fece7fe1789978ae0675cae2','engine_tag_object_sha':'308a50778fb4916ddde0d2923feea3d11dcc92c8'},
'bound':{'active_minutes':60,'tooling_minutes':15,'heavy_ci':0,'scratch_max_bytes':268435456,'minimum_free_gib':12,'build_runtime_translation_acquisition_authorized':False},
'question':'Which native/shared contacts can be removed or isolated to reduce actual MariaDB update work while retaining native contracts?',
'classification_legend':{'1':'required upstream build/hook in current route','2':'independently compiled owned glue candidate, internal dependence may remain','3':'host policy','4':'removable native-profile legacy/duplicate/experiment after proof'},
'patches':[inventory(p,p=='guest/experimental.patch') for p in patches],
'new_file_reconstruction':{'method':'Apply only five custom new-file sections and subsequent changes in patch order with patch --batch --fuzz=0 -p1; no upstream source/build','files':reconstructed},
'prepared_families':[
 {'id':'embedded-time','citations':['guest/patches/13.0.2-prepared.patch:3','guest/experimental.patch:1020','guest/experimental.patch:1061'],'native_required':'not on wire TIME path; native patch preimage expects fix','confidence':'high local branch','owner':'legacy upstream fix; exclude/rebase native profile only after proof'},
 {'id':'embedded-unsigned','citations':['guest/patches/13.0.2-prepared.patch:12','tests/fixtures/prepared-param-order-functions.json:10','guest/experimental.patch:1167'],'native_required':'not in named native selectors; native descriptor/snapshot remains independently required','confidence':'high local selectors'},
 {'id':'parameter-items-metadata','citations':['guest/patches/13.0.2-prepared.patch:24','guest/patches/13.0.2-prepared.patch:80','guest/patches/13.0.2-prepared.patch:127','guest/experimental.patch:1253'],'native_required':'no named normal native/bootstrap caller; EOF decode-counter patch must rebase; whole-program unknown','confidence':'high named route, whole-program unknown'},
 {'id':'capi-result-bind','citations':['guest/patches/13.0.2-prepared.patch:40','guest/patches/13.0.2-prepared.patch:92','guest/patches/13.0.2-prepared.patch:97'],'native_required':'legacy C API prepared families; no named normal native caller','confidence':'high named route, link removal unknown'},
 {'id':'embedded-text-metadata-oom','citations':['guest/patches/13.0.2-prepared.patch:119','guest/routine_bootstrap.inc:24','guest/routine_bootstrap.inc:89','guest/experimental.patch:54'],'native_required':True,'confidence':'high bootstrap SELECT route','owner':'retain shared upstream guard'},
 {'id':'native-conversion-snapshot','citations':['guest/experimental.patch:1634','guest/experimental.patch:1709','guest/experimental.patch:1842'],'native_required':True,'confidence':'high callsite; snapshot completeness across future upstream mutations unknown','owner':'guest Item/handler/object-representation boundary; no host decoder'}],
'unknowns':['Complete upstream NET/do_command/SQL-level prepared call graph absent; engine commit is not an object in this repo','Native omission link/build/runtime not executed','No explicit NET read-ahead admission event found in overlay; buffered-dispatch path needs complete source/targeted control','Independent active-command host watchdog not established by inspected nativewire code;8s RPC deadline is different','Real metadata allocation failure injection absent in saved trial','Archive busy cause, restore and paired legacy archive scenario unresolved','Final public tuple and C3 Linux/fault/settings acceptance pending'],
'comparison':{'functional_shared_repair_families':3,'new_native_cpp_repairs':0,'clean_producers':2,'native_original_cases_pass':79,'native_original_observations_pass':701,'additional_archive_capture':'FAIL busy, consumed=false; not proof of engine regression','total_update_burden':'INCONCLUSIVE','cost_record':'benchmarks/spikes/issue128-real/evidence/timing.json','duration_caveat':'unequal acquisition/cache/verification programs; no native speed or total-cost ranking','manual_cost_kind':'coarse prior estimates, not measured human active effort'},
'recommendation':{'change':'native preparation profile split, preserve embedded text metadata guard and native conversion snapshot','implementation_this_task':False,'adoption_selected':False,'reversal':'restore exact original profile if internally required fix lost, contracts regress, or profile maintenance adds obligations without eliminating native adapter repair/review'},
'protected_parent_files':['docs/development.md','scripts/development_scope.py','scripts/live_ci.py','tests/test_development_scope.py']}
assert len({r['target'] for r in evidence['patches'][0]['sections']})==20
for family in evidence['prepared_families']:
 for cite in family['citations']:
  path,line=cite.rsplit(':',1);assert 0<int(line)<=len(Path(path).read_text().splitlines()),cite
out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print('PASS:20 native targets,5 reconstructed custom files,6 prepared families; citations in bounds')
print('evidence_bytes',out.stat().st_size)
for item in reconstructed: print(item['target'],item['lines'],item['sha256'])
