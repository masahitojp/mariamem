import json,hashlib,re,difflib,sys
from pathlib import Path
w=Path(__file__).resolve().parents[1];root=w/'worktree';sys.path.insert(0,str(root/'scripts'))
import dev_guest,runtime_thread_lifetime as b
sha=lambda x:hashlib.sha256(x).hexdigest()
t=w/'temp/translation';guest=json.loads((w/'evidence/guest.json').read_text());raw=dev_guest.verify_translation(root,t,guest['guest_sha256']);old=json.loads((root/'docs/reviews/v06x-prepared-long-data-binding/translation-inputs.json').read_text())
for key in ('converter_commit','converter_archive_sha256','patched_converter_sha256','patches_sha256'):assert raw[key]==old[key],key
comparison={n:{'before':old['files_sha256'].get(n),'after':v,'changed':old['files_sha256'].get(n)!=v} for n,v in raw['files_sha256'].items()};assert set(raw['files_sha256'])==set(old['files_sha256'])
(w/'evidence/raw-inventory-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
r={'guest_sha256':guest['guest_sha256'],'functions':{}}
for name,(fn,expected) in b.FUNCTIONS.items():
 files=[p for p in (t/'module/generated').rglob('*_pure.go') if re.search(r'(?m)^func '+fn+r'\(',p.read_text())];assert len(files)==1
 file=files[0];body=b.function(file.read_text(),fn);fixture=(root/'tests/fixtures/prepared-p2-binding'/(fn+'.txt')).read_text()
 (w/'evidence'/(fn+'.txt')).write_text(body)
 diff=''.join(difflib.unified_diff(fixture.splitlines(True),body.splitlines(True),fromfile='previous/'+fn,tofile='new/'+fn));(w/'evidence'/(fn+'.diff')).write_text(diff)
 r['functions'][name]={'current_file':str(file.relative_to(t/'module/generated')),'normalized_sha256':sha(re.sub(r'\s+','',body).encode()),'previous_normalized_sha256':expected,'byte_identical':body==fixture}
files=[]
for p in (t/'module/generated').rglob('*_pure.go'):
 text=p.read_text()
 if 'base.MemoryInit(m, 0,' not in text:continue
 for body in re.split(r'\n(?=func Fn\d+\()',text):
  if 'base.MemoryInit(m, 0,' in body and 'base.DataDrop(m, 1)' in body:
   fn=re.search(r'func (Fn\d+)\(',body)[1];body=b.function(text,fn);files.append((p,fn,body))
assert len(files)==1
p,fn,body=files[0];(w/'evidence/memory-init.txt').write_text(body);oldinit=(root/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text();(w/'evidence/memory-init.diff').write_text(''.join(difflib.unified_diff(oldinit.splitlines(True),body.splitlines(True),fromfile='previous/init',tofile='new/init')))
r['memory_init']={'file':'code/'+str(p.relative_to(t/'module/generated')),'function':fn,'normalized_sha256':sha(re.sub(r'\s+','',body).encode()),'byte_identical':body==oldinit}
data=(t/'module/generated/data.bin').read_bytes();r['data_sha256']=sha(data);r['data_bytes']=len(data)
gen=(t/'module/generated/generated.go').read_text();r['segment_declarations']=sorted(set(re.findall(r'm.DataSegs = \[\]\[\]byte\{[^\n]+',gen)))
(w/'evidence/binding-inspection.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
