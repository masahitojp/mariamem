import hashlib,json,re
from pathlib import Path
root=Path.cwd(); task=root/'build/experiment-work/prepared-canonical';raw=task/'temp/translation/module/generated'
baseline=json.loads((root/'tests/fixtures/routine-j1-baseline.json').read_text());previous=json.loads((root/'tests/fixtures/routine-thread-layout.json').read_text())
num=re.compile(r'(?<![A-Za-z_0-9])\d+\b')
def norm(x):return re.sub(r'\s+','',x)
def shape(x):return num.sub('#',norm(re.sub(r'\bFn\d+\b','Fn',x)))
allf={};shapes={}
for p in raw.glob('p*/*_pure.go'):
 text=p.read_text();starts=list(re.finditer(r'(?m)^func Fn(\d+)\(',text))
 for i,m in enumerate(starts):
  body=text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)]
  n=int(m[1]);allf[n]=(p.relative_to(raw).as_posix(),body);shapes.setdefault(shape(body),[]).append(n)
mapping={};entries=[]
for row in previous['functions']:
 old=row['old_function'];body=baseline['functions'][str(old)]['body'];matches=shapes.get(shape(body),[])
 assert len(matches)==1,(old,matches)
 mapping[old]=matches[0]
for old,new in mapping.items():
 filename,body=allf[new];expected=re.sub(r'\bFn(\d+)\b',lambda m:'Fn'+str(mapping.get(int(m[1]),int(m[1]))),baseline['functions'][str(old)]['body'])
 assert num.sub('#',norm(expected))==num.sub('#',norm(body)),old
 changed=sorted(set((int(a),int(b)) for a,b in zip(num.findall(norm(expected)),num.findall(norm(body))) if a!=b))
 print('pairs detail',old,changed) if any(b-a != 5760 for a,b in changed) else None
 print(old,'->',new,'delta',sorted({b-a for a,b in changed}), 'pairs',len(changed))
 entries.append(dict(old_function=old,new_function=new,function='Fn'+str(new),file=filename,normalized_sha256=hashlib.sha256(norm(body).encode()).hexdigest(),integer_changes=changed,direct_calls=sorted({int(i) for i in re.findall(r'\bFn(\d+)\(',body)}-{new})))
pin=json.loads((root/'tests/fixtures/prepared-p2-binding/identity.json').read_text());delta={b-a for e in entries for a,b in e['integer_changes']}
print('ALL DELTAS',sorted(delta))
layout=dict(guest_sha256=pin['guest_sha256'],baseline_source_commit=baseline['source_commit'],baseline_guest_sha256=previous['baseline_guest_sha256'],result='Audited exact callee mapping and constant-only relocation against preserved J1 baseline; oracle execution pending',global_address_delta=5760,data_segments=[dict(offset=s['memory_offset'],begin=s['start'],end=s['end']) for s in pin['data_segments']],data_sha256=pin['data_sha256'],tls_bytes=pin['tls_bytes'],tls_sha256=pin['tls_sha256'],function_map={str(k):v for k,v in mapping.items()},functions=entries)
(task/'evidence/j1-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
