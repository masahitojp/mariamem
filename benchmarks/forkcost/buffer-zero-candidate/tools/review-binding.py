from pathlib import Path
import re,json,hashlib,sys
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp';M=T/'preflight/candidate/module';sys.path.insert(0,str(W/'scripts'))
import runtime_thread_lifetime as thread
import runtime_crc32c as crc
h=lambda b:hashlib.sha256(b).hexdigest()
record=json.loads((T/'guest/guest.json').read_text());guest=record['guest_sha256'];assert h((T/'guest/mariamem.wasm').read_bytes())==guest
names={int(n):s for n,s in (line.split(':',1) for line in (E/'function-map.txt').read_text().splitlines())}
canonical_map=(W/'docs/reviews/prepared-output-product/function-map.txt').read_text();canonical_symbols={symbol:int(n) for n,symbol in (line.split(':',1) for line in canonical_map.splitlines())}
idx={s:n for n,s in names.items()};sources={str(p.relative_to(M)):p.read_text() for p in (M/'generated').glob('p*/p*_pure.go')}
def find(index):
 fn='Fn'+str(index);found=[(name,thread.function(text,fn)) for name,text in sources.items() if re.search(r'(?m)^func '+fn+r'\(',text)];assert len(found)==1,(index,len(found));return found[0]
# Minimal candidate has no diagnostic strings or data relocation.
text=(W/'internal/generatedgo/code/generated.go').read_text();a=text.index('var wasm2goData_data_bin = []byte("')+len('var wasm2goData_data_bin = []byte("');z=text.index('")',a);olddata=bytes.fromhex(text[a:z].replace('\\x',''));newdata=(M/'generated/data.bin').read_bytes();delta_data=len(newdata)-len(olddata);assert delta_data==0
image=json.loads((W/'internal/generatedgo/image/layout.json').read_text());old_bss=image['data_end'];old_end=image['end'];workers={};symbols={};relocations={}
number=re.compile(r'(?<![A-Za-z0-9_])(\d+)(?![A-Za-z0-9_])')
for oldfn,symbol in [('Fn153','dlfree'),('Fn214','wasi_thread_start'),('Fn131','sched_yield')]:
 index=idx[symbol];assert index==int(oldfn[2:]),('worker index changed',symbol,index)
 oldpath,expected=next((p,sha) for p,(fn,sha) in thread.FUNCTIONS.items() if fn==oldfn)
 oldbody=thread.function((W/'internal/generatedgo'/oldpath).read_text(),oldfn)
 oldbody=re.sub(r'\n\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n','\n',oldbody)
 assert h(re.sub(r'\s+','',oldbody).encode())==expected
 path,body=find(index);changes=[]
 def restore(m):
  value=int(m[1])
  if old_bss+delta_data<=value<old_end+delta_data:
   changes.append([value-delta_data,value]);return str(value-delta_data)
  return m[1]
 normalized=body;assert h(re.sub(r'\s+','',normalized).encode())==expected,('worker changed beyond BSS relocation',symbol)
 assert body == normalized
 actual=h(re.sub(r'\s+','',body).encode());workers['code/'+path.removeprefix('generated/')]=[oldfn,actual];symbols[symbol]={'function':oldfn,'path':path};relocations[oldfn]={'canonical_normalized_sha256':expected,'normalized_sha256':h(re.sub(r'\s+','',normalized).encode()),'zero_initialized_bss_range':[old_bss,old_end],'delta':delta_data,'addresses':sorted(set(tuple(c) for c in changes))}
# Recover the original, pre-CRC-substitution validator from the committed oracle.
original=(W/'internal/generatedgo/code/p4/crc32c_reference_test.go').read_text();original=original[original.index('func originalCRCValidator('):].replace('func originalCRCValidator(','func '+crc.FUNCTION+'(',1);original=re.sub(r'\bp4\.(Fn\d+)\(',r'\1(',original).rstrip();assert h(original.encode())==crc.BODY_SHA256
text=(W/'internal/generatedgo/code/generated.go').read_text();a=text.index('var wasm2goData_data_bin = []byte("')+len('var wasm2goData_data_bin = []byte("');z=text.index('")',a);olddata=bytes.fromhex(text[a:z].replace('\\x',''));table=olddata[crc.TABLE_OFFSET:crc.TABLE_OFFSET+crc.TABLE_SIZE];assert h(table)==crc.TABLE_SHA256
newdata=(M/'generated/data.bin').read_bytes();offset=newdata.find(table);assert offset>=0 and newdata.find(table,offset+1)==-1
symbol='_Z21buf_page_is_corruptedbPKhj';index=idx[symbol];path,body=find(index);body=body.rstrip();newfn='Fn'+str(index);delta=offset-crc.TABLE_OFFSET
normalized_name=body.replace('func '+newfn+'(', 'func '+crc.FUNCTION+'(',1)
# Full token skeleton, labels, calls and every non-address constant must match.
assert number.sub('#',normalized_name)==number.sub('#',original),'CRC control flow/calls changed'
old_numbers=list(number.finditer(original));new_numbers=list(number.finditer(normalized_name));assert len(old_numbers)==len(new_numbers)
def segments(code_text,source_texts,data):
 cuts=[tuple(map(int,x)) for x in re.findall(r'wasm2goData_data_bin\[(\d+):(\d+)\]',next(line for line in code_text.splitlines() if 'm.DataSegs = ' in line))];assert len(cuts)==3
 addresses=set(int(x) for text in source_texts for x in re.findall(r'base.MemoryInit\(m, 1, int32\((\d+)\)',text));assert len(addresses)==1
 second=addresses.pop();third=(second+cuts[1][1]-cuts[1][0]+15)&~15
 return [(8388608,data[cuts[0][0]:cuts[0][1]]),(second,data[cuts[1][0]:cuts[1][1]]),(third,data[cuts[2][0]:cuts[2][1]])]
old_segments=segments(text,[(W/'internal/generatedgo/code/p7/p7_pure.go').read_text()],olddata)
new_segments=segments((M/'generated/generated.go').read_text(),list(sources.values()),newdata)
def initial(segments,address,n):
 out=bytearray(n)
 for start,data in segments:
  lo=max(address,start);hi=min(address+n,start+len(data))
  if lo<hi:out[lo-address:hi-address]=data[lo-start:hi-start]
 return bytes(out)
crc_relocations=[];mapping={}
for oldm,newm in zip(old_numbers,new_numbers):
 oldvalue=int(oldm[1]);newvalue=int(newm[1])
 if oldvalue==newvalue:continue
 kind=None;checkbytes=None
 if old_bss<=oldvalue<old_end and newvalue==oldvalue+delta_data:kind='zero-initialized BSS'
 elif 8388608+crc.TABLE_OFFSET<=oldvalue<8388608+crc.TABLE_OFFSET+crc.TABLE_SIZE and newvalue==oldvalue+delta:kind='exact CRC table bytes'
 elif 8388608<=oldvalue<old_bss and newvalue==oldvalue+delta_data:
  checkbytes=initial(old_segments,oldvalue,16);newbytes=initial(new_segments,newvalue,16)
  for i in range(0,16,4):
   x=int.from_bytes(checkbytes[i:i+4],'little');y=int.from_bytes(newbytes[i:i+4],'little')
   if x==y:continue
   assert 8388608<=x<old_bss and 8388608<=y<old_bss+delta_data
   xs=initial(old_segments,x,1024).split(b'\0',1)[0];ys=initial(new_segments,y,1024).split(b'\0',1)[0]
   assert 4<=len(xs)<1024 and xs==ys and all(9<=c<127 for c in xs),(x,y)
  kind='initialized data, identical words or identical string pointees'
 else:
  # Only logging format strings may have nonuniform pooled-string relocation.
  assert f'Fn12436(m, int32({oldvalue}),' in original and f'Fn12436(m, int32({newvalue}),' in normalized_name
  oldstr=initial(old_segments,oldvalue,1024).split(b'\0',1)[0];newstr=initial(new_segments,newvalue,1024).split(b'\0',1)[0]
  assert len(oldstr)>8 and oldstr==newstr and all(9<=x<127 for x in oldstr);checkbytes=oldstr;kind='identical logging format string'
 assert kind,(oldvalue,newvalue)
 if newvalue in mapping:assert mapping[newvalue]==oldvalue
 mapping[newvalue]=oldvalue;crc_relocations.append({'old':oldvalue,'new':newvalue,'kind':kind,'bytes_sha256':h(checkbytes) if checkbytes else None})
normalized=number.sub(lambda m:str(mapping.get(int(m[1]),int(m[1]))),normalized_name);assert normalized==original
proof={'result':'PASS_IDENTICAL_WORKER_CRC_BINDING','guest_sha256':guest,'guest_record_sha256':h((T/'guest/guest.json').read_bytes()),'function_map_sha256':h((E/'function-map.txt').read_bytes()),'workers':workers,'worker_symbols':symbols,'worker_relocations':relocations,'crc':{'symbol':symbol,'path':'code/'+path.removeprefix('generated/'),'function':newfn,'body_sha256':h(body.encode()),'canonical_body_sha256':crc.BODY_SHA256,'normalized_body_sha256':h(normalized.encode()),'table_offset':offset,'canonical_table_offset':crc.TABLE_OFFSET,'table_sha256':h(table),'table_size':crc.TABLE_SIZE,'delta':delta,'relocations':crc_relocations}}
(E/'binding-review.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
