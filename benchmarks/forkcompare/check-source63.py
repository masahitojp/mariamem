"""Read-only source correspondence for issue63's proposed scoped guest change."""
import hashlib,json,re,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';S=W/'temp/source63';P=W/'temp/patched63';E=W/'evidence'
def sha(b):return hashlib.sha256(b).hexdigest()
product='b3b3b46a8807482ad3f96725af86e031fe369b01'
def blob(n):return subprocess.check_output(['git','show',product+':'+n],cwd=C)
inputs=json.loads(blob('guest/input.json'));entry=inputs['patches'][0];patch=blob(entry['file']);assert sha(patch)==entry['sha256']
paths=['mysys/my_largepage.c','mysys/my_virtual_mem.c','include/my_sys.h','include/my_virtual_mem.h','storage/innobase/buf/buf0buf.cc','storage/innobase/include/buf0buf.h']
files={}
previous=json.loads(subprocess.check_output(['git','show','experiment/zero-fill-cause:benchmarks/zerofillcause/results/correspondence.json'],cwd=C))
for name in paths:
 b=(S/name).read_bytes();p=P/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 files[name]=dict(sha256=sha(b),bytes=len(b),url='https://github.com/MariaDB/server/blob/'+inputs['source_commit']+'/'+name)
 if name in previous['upstream_files']:assert files[name]['sha256']==previous['upstream_files'][name]['sha256']
parts=re.split(r'(?m)(?=^--- a/)',patch.decode())
selected=''.join(p for p in parts if p.startswith(('--- a/mysys/my_largepage.c\n','--- a/mysys/my_virtual_mem.c\n')))
assert selected.count('--- a/')==2
subprocess.run(['patch','-p1'],cwd=P,input=selected,text=True,check=True,capture_output=True)
for name in paths[:2]:
 h=sha((P/name).read_bytes());assert h==entry['after_sha256'][name];files[name]['adopted_patched_sha256']=h
buf=(P/paths[4]).read_text();vm=(P/paths[1]).read_text();large=(P/paths[0]).read_text();header=(P/paths[5]).read_text()
assert buf.count('memory_unaligned= my_virtual_mem_reserve(&size);')==1
assert 'return my_large_virtual_alloc(size);' in vm
assert 'sizeof(size_t) < 8 ? 2 << 20 : 8 << 20' in header
assert 'posix_memalign(&p, 4096, *size)' in large and 'memset(p, 0, *size)' in large
assert 'free(ptr);' in vm[vm.index('void my_virtual_mem_release'):][:200]
record=dict(result='SOURCE_CORRESPONDENCE_PASS_NOT_BUILT',issue=63,product_source_commit=product,upstream_source_commit=inputs['source_commit'],patch_sha256=sha(patch),files=files,proposed_modified_files=['mysys/my_largepage.c','include/my_sys.h','storage/innobase/buf/buf0buf.cc'],proof_scope='inspected allocation/reserve/release path and stable existing entry; no claim of whole-repository caller census',not_done=['guest source candidate','guest build','Go regeneration','allocation failure runtime verification','platform acceptance'])
(E/'source63.json').write_text(json.dumps(record,indent=2)+'\n');print('SOURCE63 PASS: six pinned files, two adopted patch after hashes, reserve/zero/release correspondence')
