from pathlib import Path
import re,json,hashlib,sys
w=Path('.');repo=w/'worktree';root=w/'temp/host/candidate/module/generated';sys.path.insert(0,str(repo/'scripts'));from runtime_thread_lifetime import function
p=repo/'tests/fixtures/issue65-wire-binding/identity.json';previous=json.loads(p.read_text());functions={};comparisons={}
for old,new,role in [('Fn153','Fn151','free'),('Fn131','Fn129','yield'),('Fn214','Fn211','entry')]:
 matches=[x for x in root.glob('p*/*pure.go') if re.search(r'^func '+new+r'\(',x.read_text(),re.M)];assert len(matches)==1
 after=function(matches[0].read_text(),new);before=(repo/'tests/fixtures/prepared-p2-binding'/(old+'.txt')).read_text();a=before.splitlines();b=after.splitlines();assert len(a)==len(b),(role,len(a),len(b));names={};numbers={}
 for left,right in zip(a,b):
  aa=re.findall(r'\bFn\d+\b',left);bb=re.findall(r'\bFn\d+\b',right);assert len(aa)==len(bb)
  for x,y in zip(aa,bb):assert names.get(x,y)==y;names[x]=y
  aa=re.findall(r'(?<![A-Za-z0-9_])\d+\b',left);bb=re.findall(r'(?<![A-Za-z0-9_])\d+\b',right);assert len(aa)==len(bb)
  for x,y in zip(aa,bb):assert numbers.get(x,y)==y;numbers[x]=y
 changed={x:y for x,y in numbers.items() if x!=y};deltas=set()
 for x,y in changed.items():
  if role=='entry' and x=='505' and y=='497':continue
  assert int(x)>15000000 and int(y)>15000000,(role,x,y);deltas.add(int(y)-int(x))
 assert len(deltas)<=1,(role,deltas)
 mapped=re.sub(r'\bFn\d+\b',lambda m:names[m[0]],before);mapped=re.sub(r'(?<![A-Za-z0-9_])\d+\b',lambda m:numbers[m[0]],mapped)
 assert re.sub(r'\s+','',mapped)==re.sub(r'\s+','',after),role
 if role=='free':assert set(re.findall(r'\bFn\d+\(m',after))=={'Fn151(m','Fn129(m'};assert 'm.G0' not in after and 'm.G1' not in after
 functions['code/'+str(matches[0].relative_to(root))]={'function':new,'normalized_sha256':hashlib.sha256(re.sub(r'\s+','',after).encode()).hexdigest(),'role':role}
 comparisons[role]={'complete_body_equal_after_recorded_relocation':True,'function_renames':names,'changed_numeric_literals':changed,'static_relocation_delta':list(deltas),'previous_body_sha256':hashlib.sha256(before.encode()).hexdigest(),'new_body_sha256':hashlib.sha256(after.encode()).hexdigest()}
 (repo/'tests/fixtures/issue65-wire-binding'/(new+'.txt')).write_text(after)
g=json.loads((w/'temp/artifact/guest.json').read_text());record={'contract':'issue65-experimental-thread-binding-v1','guest_sha256':g['guest_sha256'],'previous_experimental_guest_sha256':previous['guest_sha256'],'functions':functions,'review':comparisons,'ABI_offsets':{'start_args.pthread':16,'pthread.map_base':40,'pthread.map_size':44},'status':'experimental exact-function binding; canonical binding unchanged'}
p.write_text(json.dumps(record,indent=2)+'\n');(w/'evidence/binding-review/final-refresh.json').write_text(json.dumps(record,indent=2)+'\n');print('Reviewed complete worker bodies for',g['guest_sha256'])
