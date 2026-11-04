"""Exact accepted closure proof: only BSS relocation and one identical C string.
No fuzzy function search, new call-map inference or instruction normalization.
"""
from pathlib import Path
import json,re,hashlib,sys,copy
w=Path(__file__).resolve().parents[1];s=w/'temp/source';e=w/'evidence';module=w/'temp/abi-preflight/candidate/module';sys.path.insert(0,str(s/'scripts'));import runtime_thread_lifetime as binding
ROLE_MAP={'Fn219':('p3/p3_pure.go','Fn219'),'Fn4068':('p7/p7_pure.go','Fn4069')}
fixture=json.loads((s/'tests/fixtures/routine-thread-layout.json').read_text());oldtext=(s/'internal/generatedgo/code/generated.go').read_text();newtext=(module/'generated/generated.go').read_text()
m=re.search(r'var wasm2goData_data_bin = \[\]byte\("(.*?)"\)',oldtext,re.S);assert m
olddata=bytes.fromhex(m[1].replace('\\x',''));newdata=(module/'generated/data.bin').read_bytes()
def slices(text):
 matches=re.findall(r'm\.DataSegs = \[\]\[\]byte\{([^}]+)\}',text);assert matches
 result=re.findall(r'wasm2goData_data_bin\[(\d+):(\d+)\]',matches[0]);assert len(result)==3
 assert all(re.findall(r'wasm2goData_data_bin\[(\d+):(\d+)\]',x)==result for x in matches)
 return [(int(a),int(b)) for a,b in result]
oldsegs=slices(oldtext);newsegs=slices(newtext)
assert oldsegs[-1][1]==len(olddata) and newsegs[-1][1]==len(newdata)
assert [b-a for a,b in oldsegs][1:]==[b-a for a,b in newsegs][1:]==[642620,505]
assert newdata[slice(*newsegs[2])]==olddata[slice(*oldsegs[2])]
assert hashlib.sha256(olddata[slice(*oldsegs[2])]).hexdigest()==fixture['tls_sha256']
def oldbody(f):
 b=binding.function((s/'internal/generatedgo/code'/f['file']).read_text(),f['function'])
 if f['function']=='Fn153':
  anchor='\tif base.DeferThreadAllocationFree(m, l0) {\n\t\treturn\n\t}\n';assert b.count(anchor)==1;b=b.replace(anchor,'',1)
 assert digestbody(b)==f['normalized_sha256'];return b
def digestbody(body):return hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest()
def tokens(b):return re.findall(r'0[xX][\da-fA-F]+|\d+|[A-Za-z_]\w*|[^\w\s]',b)
def number(v):return int(v,0) if re.fullmatch(r'0[xX][\da-fA-F]+|\d+',v) else None
def ctor(b):
 fill=re.findall(r'base.MemoryFill\(m, int32\((\d+)\), \w+, int32\((\d+)\)\)',b);assert len(fill)==1
 tls=re.findall(r'(v\d+) = int32\((\d+)\)\s+m.G1 = \1',b);assert len(tls)==1
 copies=re.findall(r'base.MemoryInit\(m, ([01]), int32\((\d+)\), \w+, int32\((\d+)\)\)',b);assert [i for i,a,n in copies]==['0','1']
 return {'bss_start':int(fill[0][0]),'bss_bytes':int(fill[0][1]),'tls_start':int(tls[0][1]),'copies':[(int(a),int(n)) for i,a,n in copies]}
a=binding.function((s/'internal/generatedgo/code/p7/p7_pure.go').read_text(),'Fn67');b=binding.function((module/'generated/p7/p7_pure.go').read_text(),'Fn67');oc=ctor(a);nc=ctor(b);delta=nc['bss_start']-oc['bss_start'];assert delta>0 and delta%16==0
assert nc['bss_bytes']==oc['bss_bytes'] and nc['tls_start']-oc['tls_start']==delta
assert nc['copies'][0][0]==oc['copies'][0][0]==8388608
assert nc['copies'][1][0]-oc['copies'][1][0]==delta
assert nc['copies'][0][1]==newsegs[0][1]-newsegs[0][0] and nc['copies'][1][1]==642620
# Every changed mutable-global literal must point into the same zeroed BSS,
# using the delta independently fixed by the initializer's BSS/TLS coordinates.
def compare(before,after,constructor=False):
 # Exact named role map: one function's ordinal and one package placement.
 # Verify the entire body/call graph after this explicit symbol substitution.
 before=re.sub(r'\bFn4068\b','Fn4069',before)
 x=tokens(before);y=tokens(after);assert len(x)==len(y),'instruction/token count changed';changes=[]
 for left,right in zip(x,y):
  p=number(left);q=number(right)
  required=(p is not None and ((15244865<=p<=15471936 or (constructor and p in [oc['bss_start'],oc['bss_start']+oc['bss_bytes']])) or p==8688301 or (constructor and p in [oc['copies'][1][0],oc['tls_start'],oc['copies'][0][1]])))
  if left==right and not required:continue
  assert p is not None and q is not None,('nonliteral/call change',left,right)
  if (15244865<=p<=15471936 or (constructor and p in [oc['bss_start'],oc['bss_start']+oc['bss_bytes']])):
   assert q-p==delta,('BSS relocation mismatch',p,q)
  elif constructor and p in [oc['copies'][1][0],oc['tls_start']]:assert q-p==delta
  elif constructor and p==oc['copies'][0][1]:assert q==nc['copies'][0][1]
  elif p==8688301: # Sole accepted read-only string literal in this closure.
   def cstring(data,segs,addr,base):
    n=addr-base;assert 0<=n<segs[0][1];end=data.index(b'\0',n);assert end-n<4096;return data[n:end+1]
   assert cstring(olddata,oldsegs,p,8388608)==cstring(newdata,newsegs,q,8388608)
  else:raise AssertionError(('unexpected changed immediate',p,q))
  changes.append([p,q])
 return changes
constructor_changes=compare(a,b,True)
rows=[]
for f in fixture['functions']:
 before=oldbody(f);file,fn=ROLE_MAP.get(f['function'],(f['file'],f['function']));after=binding.function((module/'generated'/file).read_text(),fn);changes=compare(before,after);rows.append({'baseline_file':f['file'],'baseline_function':f['function'],'file':file,'function':fn,'normalized_sha256':digestbody(after),'integer_changes':changes})
# Same stack/TLS globals and allocation layout. New aliases outside this owner
# are ordinary compiler data; no handwritten worker offsets were changed.
for key in range(4):
 pat=rf'm.G{key} = int32\((-?\d+)\)';x=re.findall(pat,oldtext);y=re.findall(pat,newtext);assert x and x==y,(key,x,y)
# Rejection controls cannot be disguised as permitted address relocations.
first=fixture['functions'][0];before=oldbody(first);after=binding.function((module/'generated'/first['file']).read_text(),first['function'])
try:compare(before,after.replace('func '+first['function'],'func WrongFunction',1))
except AssertionError:pass
else:raise AssertionError('call/instruction mutation accepted')
try:compare(before,after+'\nreturn 1\n')
except AssertionError:pass
else:raise AssertionError('extra instruction accepted')
result={'result':'PASS_EXACT_RELOCATION_ONLY','source_commit':json.loads((e/'build-source.json').read_text())['source_commit'],'guest_sha256':json.loads((w/'temp/dev-guest/guest.json').read_text())['guest_sha256'],'explicit_role_map':ROLE_MAP,'bss_delta':delta,'old_initializer':oc,'new_initializer':nc,'constructor_integer_changes':constructor_changes,'functions':rows,'tls_sha256':fixture['tls_sha256'],'tls_bytes':505,'data_sha256':hashlib.sha256(newdata).hexdigest(),'negative_controls':['changed function/call token rejected','extra instruction rejected'],'scope':'exact accepted nineteen-body owner closure, unchanged call graph and immediates except proven same zeroed BSS relocation / one byte-identical read-only C string; TLS bytes/G0-G3 unchanged; no generic ABI support'}
(e/'worker-relocation-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['result','bss_delta','tls_bytes']},indent=2))
