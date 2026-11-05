from pathlib import Path
import re,json,hashlib
w=Path('.');e=w/'evidence/binding-review';pins=json.loads((e/'functions.json').read_text());functions={};comparisons={}
for old,new,role in [('Fn153','Fn151','free'),('Fn131','Fn129','yield'),('Fn214','Fn211','entry')]:
 before=(w/'worktree/tests/fixtures/prepared-p2-binding'/(old+'.txt')).read_text();after=(e/(new+'.txt')).read_text();a=before.splitlines();b=after.splitlines();assert len(a)==len(b)
 names={};numbers={}
 for left,right in zip(a,b):
  an=re.findall(r'\bFn\d+\b',left);bn=re.findall(r'\bFn\d+\b',right);assert len(an)==len(bn)
  for x,y in zip(an,bn):assert names.get(x,y)==y;names[x]=y
  ai=re.findall(r'(?<![A-Za-z0-9_])\d+\b',left);bi=re.findall(r'(?<![A-Za-z0-9_])\d+\b',right);assert len(ai)==len(bi)
  for x,y in zip(ai,bi):assert numbers.get(x,y)==y;numbers[x]=y
 changed={x:y for x,y in numbers.items() if x!=y}
 for x,y in changed.items():assert (int(x)>15000000 and int(y)==int(x)-1088) or (role=='entry' and x=='505' and y=='497'),(role,x,y)
 mapped=re.sub(r'\bFn\d+\b',lambda m:names[m[0]],before)
 mapped=re.sub(r'(?<![A-Za-z0-9_])\d+\b',lambda m:numbers[m[0]],mapped)
 assert re.sub(r'\s+','',mapped)==re.sub(r'\s+','',after),role
 if role=='free':assert set(re.findall(r'\bFn\d+\(m',after))=={'Fn151(m','Fn129(m'};assert 'm.G0' not in after and 'm.G1' not in after
 functions[pins[new]['file']]={'function':new,'normalized_sha256':pins[new]['normalized_sha256'],'role':role}
 comparisons[role]={'full_body_equal_after_explicit_relocation':True,'function_renames':names,'changed_numeric_literals':changed,'old_sha256':hashlib.sha256(before.encode()).hexdigest(),'new_sha256':hashlib.sha256(after.encode()).hexdigest()}
guest=json.loads((w/'temp/artifact/guest.json').read_text())
fixture=w/'worktree/tests/fixtures/issue65-wire-binding';fixture.mkdir(parents=True)
for fn in pins: (fixture/(fn+'.txt')).write_text((e/(fn+'.txt')).read_text())
record={'contract':'issue65-experimental-thread-binding-v1','guest_sha256':guest['guest_sha256'],'functions':functions,'review':comparisons,'ABI_offsets':{'start_args.pthread':16,'pthread.map_base':40,'pthread.map_size':44},'runtime_adapter':'unchanged completion owner; exact new free entry before allocator; same sole yield callee','status':'experimental exact binding; not production adoption'}
(fixture/'identity.json').write_text(json.dumps(record,indent=2)+'\n');(e/'review.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'guest_sha256':guest['guest_sha256'],'roles':{v['role']:v['function'] for v in functions.values()},'review':'complete bodies equivalent after recorded function renames, -1088 static relocation and TLS505->497'},indent=2))
