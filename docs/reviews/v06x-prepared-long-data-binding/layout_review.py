import json,re,hashlib
from pathlib import Path
w=Path(__file__).resolve().parents[1]; root=w/'worktree'; evidence=w/'evidence'
old=json.loads((root/'tests/fixtures/prepared-p2-binding/identity.json').read_text())
review={'functions':{}}
nums=lambda s:re.findall(r'\b\d+\b',s)
structure=lambda s:re.sub(r'\b\d+\b','#',s)
for fn in ('Fn153','Fn131','Fn214'):
 a=(root/'tests/fixtures/prepared-p2-binding'/(fn+'.txt')).read_text();b=(evidence/(fn+'.txt')).read_text()
 assert structure(a)==structure(b), fn+' nonnumeric structure changed'
 pairs=[(int(x),int(y)) for x,y in zip(nums(a),nums(b)) if x!=y]
 review['functions'][fn]={'non_numeric_structure_identical':True,'changed_literal_occurrences':len(pairs),'literal_pairs':sorted(set(pairs)),'deltas':sorted(set(y-x for x,y in pairs))}
a=(root/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text();b=(evidence/'memory-init.txt').read_text();assert structure(a)==structure(b),'initializer structure changed'
review['memory_init_changes']={'non_numeric_structure_identical':True,'literal_pairs':[(int(x),int(y)) for x,y in zip(nums(a),nums(b)) if x!=y]}
data=(w/'temp/translation/module/generated/data.bin').read_bytes();inspection=json.loads((evidence/'binding-inspection.json').read_text());declaration=inspection['segment_declarations'];assert len(declaration)==1
ranges=[tuple(map(int,x)) for x in re.findall(r'wasm2goData_data_bin\[(\d+):(\d+)\]',declaration[0])];assert len(ranges)==3
review['data_sha256']=hashlib.sha256(data).hexdigest(); review['data_segments']=[{'start':x,'end':y,'sha256':hashlib.sha256(data[x:y]).hexdigest()} for x,y in ranges]
review['TLS_bytes']=ranges[2][1]-ranges[2][0];review['TLS_content_identical_to_previous']=review['data_segments'][2]['sha256']==old['tls_sha256'];assert review['TLS_bytes']==505 and review['TLS_content_identical_to_previous']
(evidence/'layout-review.json').write_text(json.dumps(review,indent=2)+'\n');print(json.dumps(review,indent=2))
