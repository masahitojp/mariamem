from pathlib import Path
import json,re,hashlib,sys,collections,ast,difflib,subprocess
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence'
sys.path.insert(0,str(S/'scripts'));import runtime_thread_lifetime as thread;import runtime_crc32c as crc
from git_identity import require_commit
require_commit(S,'b1a265cc30a8603ced743c8aeb59c752751ff9d6')
H=lambda b:hashlib.sha256(b).hexdigest();compact=lambda s:re.sub(r'\s+','',s)
OLD='example.com/mariamem-spike/generated';NEW='github.com/masahitojp/mariamem/internal/generatedgo/code'
raws={};reports={};paths={}
for platform in ['ubuntu','macos']:
 root=T/platform;man=next(root.glob('**/translation/input-manifest.json'));raw=json.loads(man.read_text());p=man.parent/'module/generated';result=json.loads(next(root.glob('**/build/lexer-ci/result.json')).read_text())
 assert result['source_commit']=='b1a265cc30a8603ced743c8aeb59c752751ff9d6' and result['result']=='PASS_INPUT_AND_TRANSLATION_ONLY'
 assert result['guest_sha256']==raw['guest_sha256']=='14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1'
 assert raw['files_sha256']=={str(q.relative_to(p)):H(q.read_bytes()) for q in sorted(p.rglob('*')) if q.is_file()}
 raws[platform]=raw;paths[platform]=p;reports[platform]=result
assert {k for k in raws['ubuntu'] if raws['ubuntu'][k]!=raws['macos'][k]}=={'patched_converter_sha256'},'unexpected cross-host translation difference'
assert raws['ubuntu']['files_sha256']==raws['macos']['files_sha256']
base=paths['ubuntu'];baseline=json.loads((S/'release/generated-go-translation.json').read_text())
unchanged={n:h for n,h in raws['ubuntu']['files_sha256'].items() if baseline['files_sha256'].get(n)==h}
changed=sorted(set(raws['ubuntu']['files_sha256'])-set(unchanged));assert all(n in baseline['files_sha256'] for n in raws['ubuntu']['files_sha256'])
functions={};raw_functions=E/'functions';raw_functions.mkdir(exist_ok=True)
for rel,(name,expected) in thread.FUNCTIONS.items():
 old=thread.function((S/'internal/generatedgo'/rel).read_text(),name)
 if name=='Fn153':old=re.sub(r'\n\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n','\n',old,count=1)
 assert H(compact(old).encode())==expected
 new=thread.function((base/rel.removeprefix('code/')).read_text().replace(OLD,NEW),name)
 # Token-for-token comparison: only decimal numeric tokens may differ. No
 # identifier/call/control-flow/literal/operator is normalized away.
 token=lambda v:re.findall(r'\d+|[^\d]+',v)
 aa,bb=token(old),token(new);assert len(aa)==len(bb)
 changes=collections.Counter()
 for a,b in zip(aa,bb):
  if a==b:continue
  assert a.isdecimal() and b.isdecimal() and int(b)-int(a)==14464,(name,a,b)
  changes[(int(a),int(b))]+=1
 assert ''.join(str(int(a)+14464) if (a.isdecimal() and (int(a),int(a)+14464) in changes) else a for a in aa)==new
 (raw_functions/(name+'.go.txt')).write_text(new)
 functions[rel]={'name':name,'old_normalized_sha256':expected,'new_normalized_sha256':H(compact(new).encode()),'new_exact_sha256':H(new.encode()),'replacements':[{'old':a,'new':b,'occurrences':n} for (a,b),n in sorted(changes.items())],'non_address_bytes':'EXACT_MATCH','function_name':'UNCHANGED'}
# CRC uses an exact body hash (not whitespace normalized).
text=(base/'p4/p4_pure.go').read_text().replace(OLD,NEW);new=thread.function(text,'Fn18145');old=(S/'tests/fixtures/pinned-crc-validator.go.txt').read_text();assert H(old.encode())==crc.BODY_SHA256

aa,bb=token(old),token(new);assert len(aa)==len(bb),(len(aa),len(bb));moves=collections.Counter()
for a,b in zip(aa,bb):
 if a==b:continue
 assert a.isdecimal() and b.isdecimal() and (int(b)-int(a)==14464 or (a,b)==('8828555','8828619')),(a,b)
 moves[(int(a),int(b))]+=1
move_map={a:b for a,b in moves}
assert ''.join(str(move_map[int(a)]) if a.isdecimal() and int(a) in move_map else a for a in aa)==new
(raw_functions/'Fn18145.go.txt').write_text(new)
data=(base/'data.bin').read_bytes();table=bytes.fromhex((S/'tests/fixtures/pinned-crc-table.hex').read_text());at=data.find(table);assert at>=0 and data.find(table,at+1)<0 and at==crc.TABLE_OFFSET+14464
assert H(data[at:at+4096])==crc.TABLE_SHA256
c={'path':crc.PATH,'function':crc.FUNCTION,'old_exact_sha256':crc.BODY_SHA256,'new_exact_sha256':H(new.encode()),'replacements':[{'old':a,'new':b,'occurrences':n} for (a,b),n in sorted(moves.items())],'non_address_bytes':'EXACT_MATCH','table_sha256':crc.TABLE_SHA256,'table_bytes':4096,'old_table_offset':crc.TABLE_OFFSET,'new_table_offset':at,'table_matches':1}
# Pin memory initialization, TLS and address-region correspondence too.
old_generated=(S/'internal/generatedgo/code/generated.go').read_text()
literal=old_generated.split('var wasm2goData_data_bin = []byte(',1)[1].split('\n',1)[0][:-1]
old_data=ast.literal_eval(literal).encode('latin1')
identity=json.loads((S/'tests/fixtures/prepared-p2-binding/identity.json').read_text())
assert H(old_data)==identity['data_sha256']
old_tls=old_data[identity['data_segments'][2]['start']:identity['data_segments'][2]['end']]
assert old_tls==data[-505:] and H(old_tls)==identity['tls_sha256']
old_init=thread.function((S/'internal/generatedgo/code/p7/p7_pure.go').read_text(),'Fn67')
new_init=thread.function((base/'p7/p7_pure.go').read_text(),'Fn67')
assert H(compact(old_init).encode())==identity['memory_init']['normalized_sha256']
init_moves={26981552:26996016,8967206:8981670,17355840:17370304,17998464:18012928,17998976:18013440}
assert re.sub(r'\b[0-9]+\b',lambda m:str(init_moves.get(int(m[0]),int(m[0]))),old_init)==new_init
(raw_functions/'Fn67.go.txt').write_text(new_init)
# The unchanged scalar or zero-initialized BSS location represented by each
# inspected move must stay at the same offset inside its relocated region.
regions=[{'name':'data0','old_start':8388608,'old_length':8967206,'old_data':0,'new_start':8388608,'new_length':8981670,'new_data':0},
 {'name':'data1','old_start':17355840,'old_length':642620,'old_data':8967206,'new_start':17370304,'new_length':642620,'new_data':8981670},
 {'name':'bss','old_start':17998976,'old_length':8982576,'old_data':None,'new_start':18013440,'new_length':8982576,'new_data':None}]
address_proof=[]
for old_addr,new_addr in sorted(set(moves)|{(r['old'],r['new']) for f in functions.values() for r in f['replacements']}):
 if (old_addr,new_addr)==(8828555,8828619):
  oa=old_addr-8388608;na=new_addr-8388608;z=old_data.index(0,oa)+1;nz=data.index(0,na)+1
  assert old_data[oa:z]==data[na:nz]
  address_proof.append({'old':old_addr,'new':new_addr,'kind':'exact NUL-terminated diagnostic string','bytes':z-oa,'sha256':H(old_data[oa:z])});continue
 region=next(r for r in regions if r['old_start']<=old_addr<r['old_start']+r['old_length'])
 if region['name']=='data0':
  assert 15555072<=old_addr<15555072+4096 and new_addr-old_addr==14464
  address_proof.append({'old':old_addr,'new':new_addr,'kind':'same relative offset in identical full CRC table','table_offset':old_addr-15555072});continue
 assert new_addr-region['new_start']==old_addr-region['old_start']
 if region['name']=='bss':
  address_proof.append({'old':old_addr,'new':new_addr,'kind':'same relative offset in unchanged-length zeroed BSS','region_offset':old_addr-region['old_start']});continue
 # CRC table reads retain the same complete 4096-byte table (checked above).
 width=4
 oi=old_addr-region['old_start']+region['old_data'];ni=new_addr-region['new_start']+region['new_data']
 if old_data[oi:oi+width]!=data[ni:ni+width]:
  old_ptr=int.from_bytes(old_data[oi:oi+4],'little');new_ptr=int.from_bytes(data[ni:ni+4],'little')
  assert (old_ptr,new_ptr)==(8826661,8826725)
  x=old_ptr-8388608;y=new_ptr-8388608;z=old_data.index(0,x)+1;nz=data.index(0,y)+1
  assert old_data[x:z]==data[y:nz]
  address_proof.append({'old':old_addr,'new':new_addr,'kind':'same data-region offset; pointer to identical recovery diagnostic string','old_pointer':old_ptr,'new_pointer':new_ptr,'string_bytes':z-x,'string_sha256':H(old_data[x:z])})
 else:address_proof.append({'old':old_addr,'new':new_addr,'kind':'same data-region offset and unchanged first scalar','bytes':width,'sha256':H(old_data[oi:oi+width])})
memory={'old_init_compact_sha256':identity['memory_init']['normalized_sha256'],'new_init_compact_sha256':H(compact(new_init).encode()),'address_and_length_moves':init_moves,'initial_stack_base':8388608,'tls_bytes':505,'tls_sha256':H(old_tls),'BSS_bytes_unchanged':8982576,'relocated_address_proof':address_proof}
# Existing strict installer helpers all match the new runtime helper preimages.
import runtime_atomic_loads,runtime_memfs,runtime_failure,runtime_write
sys.path.insert(0,str(S/'benchmarks/spikes/generated-go-integration'));import patch_memfs
helper=patch_memfs.apply((base/'base/base.go').read_text()).replace(OLD,NEW)
helper=subprocess.run(['gofmt'],input=helper,text=True,capture_output=True,check=True).stdout
helper=runtime_atomic_loads.apply(helper);helper=runtime_memfs.apply(helper);helper=thread.apply('code/base/base.go',helper);helper=runtime_failure.apply('code/base/base.go',helper);helper=runtime_write.apply('code/base/base.go',helper)
helper=subprocess.run(['gofmt'],input=helper,text=True,capture_output=True,check=True).stdout
old_helper=(S/'internal/generatedgo/code/base/base.go').read_text()
pattern=re.compile(r'(?ms)^func (Simd_p_fx[0-9]+)\(.*?^}')
simd_old={m[1]:m[0] for m in pattern.finditer(old_helper)};simd_new={m[1]:m[0] for m in pattern.finditer(helper)}
assert set(simd_old)==set(simd_new)
strip=lambda v:pattern.sub(lambda m:'SIMD_SPECIALIZATION '+m[1],v)
assert strip(old_helper)==strip(helper),'generic runtime helper changed'
simd_changed=[name for name in simd_old if simd_old[name]!=simd_new[name]]
simd={'specializations':len(simd_old),'changed_count':len(simd_changed),'changed_names':simd_changed,'generic_base_bytes_excluding_SIMD':'EXACT_MATCH','old_adapted_sha256':H(old_helper.encode()),'new_adapted_sha256':H(helper.encode()),'limits':'Guest-specialized SIMD bodies include real generated changes and were not asserted equivalent. They remain untouched raw compiler output, bound by the complete new inventory. Actual guest table/SQL/worker controls remain required.'}
for name,template,apply in [('base/relative.go','relative-fd-base.go.txt',runtime_memfs.apply_relative),('base/prepared_files.go','prepared-files.go.txt',runtime_memfs.apply_mapping)]:
 transformed=apply((S/'benchmarks/spikes/generated-go-integration'/template).read_text().replace(OLD,NEW));transformed=subprocess.run(['gofmt'],input=transformed,text=True,capture_output=True,check=True).stdout;assert transformed==(S/'internal/generatedgo/code'/name).read_text()
result={'result':'EXACT_TRANSLATION_AND_RELOCATION_INSPECTION_PASS','source_commit':'b1a265cc30a8603ced743c8aeb59c752751ff9d6','guest_sha256':raws['ubuntu']['guest_sha256'],'both_hosts_generated_files':len(raws['ubuntu']['files_sha256']),'both_hosts_identical':True,'unchanged_raw_files':unchanged,'changed_raw_files':changed,'data_bytes':len(data),'data_sha256':H(data),'address_delta':14464,'diagnostic_string_delta':64,'memory_initialization':memory,'host_converter_binaries':{k:raws[k]['patched_converter_sha256'] for k in raws},'thread_functions':functions,'crc':c,'runtime_helper_preimages':'PASS; exact strict preimages after normal source adaptation/gofmt; generic base, relative.go and prepared_files.go byte-equal canonical; specialized SIMD compiler output is separately inventoried, not asserted equivalent','SIMD_specializations':simd,'actual_guest_acceptance':'NOT_RUN','bindings_installed':'NO; original guards unchanged','scope':'Offline exact correspondence only. Numeric relocation comparison is a recorded inspection, not a fuzzy runtime acceptance rule.'}
(E/'binding-inspection.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
