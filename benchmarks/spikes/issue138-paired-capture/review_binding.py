from pathlib import Path
import hashlib,json,re,sys
owner=Path.cwd();variant=sys.argv[1];w=owner/'build/issue128-real/temp/runtime'/variant;repo=w/'worktree';root=w/'temp/host/candidate/module/generated';sys.path.insert(0,str(repo/'scripts'))
from runtime_thread_lifetime import function
from common import digest
record=json.loads((owner/'build/issue128-real/temp'/variant/'output/artifact/guest.json').read_text());dest=w/'evidence/reviewed-binding';dest.mkdir(exist_ok=False)
def shape(text):
 return re.sub(r'\s+','',re.sub(r'(?<![A-Za-z0-9_])\d+\b','NUMBER',re.sub(r'\bFn\d+\b','FN',text)))
index={}
for file in root.glob('p*/*pure.go'):
 text=file.read_text();starts=list(re.finditer(r'^func (Fn\d+)\(',text,re.M))
 for i,m in enumerate(starts):
  chunk=text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)];body=chunk[:chunk.rfind('\n}')+2];index.setdefault(shape(body),[]).append((file,m[1]))
functions={};reviews={};tls=re.search(r'm.G2 = int32\((\d+)\)',(root/'generated.go').read_text());assert tls;tls=int(tls[1])
for old,role in [('Fn153','free'),('Fn131','yield'),('Fn214','entry')]:
 before=(repo/'tests/fixtures/prepared-p2-binding'/(old+'.txt')).read_text();found=index.get(shape(before),[]);assert len(found)==1,(role,found)
 file,new=found[0];after=function(file.read_text(),new);a=before.splitlines();b=after.splitlines();assert len(a)==len(b)
 names={};numbers={};noop=None
 for left,right in zip(a,b):
  if role=='entry' and left=='\tif v152 == int32(12) {':
   match=re.fullmatch(r'\tif v152 == int32\((\d+)\) \{',right);assert match;new_index=int(match[1]);noop={'old_index':12,'new_index':new_index};left=right
  for expression,mapping in [(r'\bFn\d+\b',names),(r'(?<![A-Za-z0-9_])\d+\b',numbers)]:
   aa=re.findall(expression,left);bb=re.findall(expression,right);assert len(aa)==len(bb)
   for x,y in zip(aa,bb):assert mapping.get(x,y)==y,(role,x,y);mapping[x]=y
 changes={x:y for x,y in numbers.items() if x!=y}
 for x,y in changes.items():
  if role=='entry' and x=='505' and int(y)==tls:continue
  assert int(x)>15000000 and int(y)>15000000,(role,x,y)
  assert (int(y)-int(x))%4==0,(role,x,y)
 static={x:y for x,y in changes.items() if int(x)>15000000};assert len(set(static.values()))==len(static)
 mapped=before
 if noop:
  mapped=mapped.replace('\tif v152 == int32(12) {',f'\tif v152 == int32({noop["new_index"]}) {{')
  oldbody=function((repo/'internal/generatedgo/code/p8/p8_pure.go').read_text(),'Fn133');assert re.sub(r'\s+','',oldbody)=='funcFn133(m*base.Module,l0int32){return}'
  candidates=[]
  for table in root.glob('p*/*.go'):
   candidates += re.findall(r'm.T0\['+str(noop['new_index'])+r'\] = (Fn\d+)\n',table.read_text())
  assert len(candidates)==1,candidates
  new_noop=candidates[0];matched=[]
  for source in root.glob('p*/*pure.go'):
   if re.search(r'^func '+new_noop+r'\(',source.read_text(),re.M):matched.append(source)
  assert len(matched)==1
  newbody=function(matched[0].read_text(),new_noop);assert re.sub(r'\s+','',oldbody.replace('Fn133',new_noop))==re.sub(r'\s+','',newbody)
  noop.update(old_function='Fn133',new_function=new_noop,old_body_sha256=hashlib.sha256(oldbody.encode()).hexdigest(),new_body_sha256=hashlib.sha256(newbody.encode()).hexdigest())
 mapped=re.sub(r'\bFn\d+\b',lambda m:names[m[0]],mapped);mapped=re.sub(r'(?<![A-Za-z0-9_])\d+\b',lambda m:numbers[m[0]],mapped)
 assert re.sub(r'\s+','',mapped)==re.sub(r'\s+','',after),role
 (dest/(new+'.txt')).write_text(after)
 functions['code/'+str(file.relative_to(root))]={'function':new,'normalized_sha256':hashlib.sha256(re.sub(r'\s+','',after).encode()).hexdigest(),'role':role}
 reviews[role]={'complete_body_equal_after_recorded_relocation':True,'function_renames':names,'changed_numeric_literals':changes,'canonical_body_sha256':hashlib.sha256(before.encode()).hexdigest(),'candidate_body_sha256':hashlib.sha256(after.encode()).hexdigest(),'tls_init_bytes':tls,'table_pointer_relocation':noop,'discovery_shape_is_not_a_validation_oracle':True,'small_constants_and_ABI_offsets_preserved':True}
result={'contract':'issue65-experimental-thread-binding-v1','guest_sha256':record['guest_sha256'],'source_commit':record['source_commit'],'target_source_commit':record['target_source_commit'],'functions':functions,'review':reviews,'ABI_offsets':{'start_args.pthread':16,'pthread.map_base':40,'pthread.map_size':44},'status':'Exact new guest function bodies reviewed; UNQUALIFIED experimental target only'}
(dest/'identity.json').write_text(json.dumps(result,indent=2)+'\n');print('Exact worker bodies reviewed',record['guest_sha256'],functions,'TLS',tls)
