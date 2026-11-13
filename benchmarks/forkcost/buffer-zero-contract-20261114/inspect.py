from pathlib import Path
import json,hashlib,re,subprocess,shutil
E=Path(__file__).resolve().parent;W=E.parent/'worktree';S=E.parent/'temp/source';P=E.parent/'temp/patched';P.mkdir(exist_ok=True)
records=json.loads((E/'source-files.json').read_text())
for r in records:assert hashlib.sha256((S/r['file']).read_bytes()).hexdigest()==r['sha256']
selected=['mysys/my_largepage.c','mysys/my_virtual_mem.c','storage/innobase/buf/buf0buf.cc']
for n in selected:
 d=P/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/n,d)
patches=[]
for name in ['guest/patches/common-portability.patch','guest/patches/12.3.3-buffer-alignment.patch']:
 data=(W/name).read_text();parts=re.split(r'(?m)(?=^--- )',data);chosen=[]
 for part in parts:
  if part.startswith('--- a/') and part.splitlines()[0][6:] in selected:chosen.append(part)
 f=E.parent/'temp'/Path(name).name;f.write_text(''.join(chosen));r=subprocess.run(['patch','-p1','--batch','--forward','-i',str(f.resolve())],cwd=P,text=True,capture_output=True,check=True);patches.append({'file':name,'sha256':hashlib.sha256((W/name).read_bytes()).hexdigest(),'output':r.stdout})
b=(P/'storage/innobase/buf/buf0buf.cc').read_text();v=(P/'mysys/my_virtual_mem.c').read_text();a=(P/'mysys/my_largepage.c').read_text();h=(S/'storage/innobase/include/buf0buf.h').read_text();l=(S/'storage/innobase/buf/buf0lru.cc').read_text()
assert 'ut_ad(!memcmp(block, field_ref_zero, sizeof *block));' in b
assert 'NOT_USED= 0' in h
assert 'memset((void*) block, 0, (extent_end - block) * sizeof *block);' in b
assert 'my_large_virtual_alloc_aligned(\n        &size, innodb_buffer_pool_extent_size)' in b
assert re.search(r'posix_memalign\(&p, alignment, \*size\).*?memset\(p, 0, \*size\)',a,re.S)
commit=v[v.index('char *my_virtual_mem_commit'):v.index('void my_virtual_mem_decommit')]
assert re.search(r'if \(!ptr\).*?memset\(p, 0, size\);.*?ptr= p;\s*}\s*update_malloc_size\(size, 0\);\s*return ptr;',commit,re.S)
assert re.search(r'defined\(__wasi__\).*?\(void\) ptr;\s*update_malloc_size\(-\(longlong\) size, 0\);\s*return;',v[v.index('void my_virtual_mem_decommit'):],re.S)
assert re.search(r'defined\(__wasi__\).*?free\(ptr\);\s*return;',v[v.index('void my_virtual_mem_release'):],re.S)
free=l[l.index('buf_LRU_block_free_non_file_page('):];free=free[free.index('buf_LRU_block_free_non_file_page('):] # first call may precede definition; exact snippet exported below
# Generated code supplies the compiled 32-bit descriptor stride, not host sizeof.
rel='code/p0/p0_pure.go';g=W/'internal/generatedgo'/rel;prov=json.loads((W/'internal/generatedgo/provenance.json').read_text());assert hashlib.sha256(g.read_bytes()).hexdigest()==prov['files_sha256'][rel]
gs=g.read_text().splitlines();assert 'v3090-v3104*v3080)*int32(232)' in '\n'.join(gs[675500:675620])
extent=2<<20;pool=16<<20;descriptor=232;page=1<<14;first_page=extent//page-extent//(page+descriptor);pages=extent//page-first_page;n=pool//extent*pages;zero=n*descriptor
layout={'pool_bytes':pool,'extent_bytes':extent,'page_bytes':page,'compiled_descriptor_bytes':descriptor,'extents':pool//extent,'frames_per_extent':pages,'first_frame_offset':first_page*page,'descriptors':n,'descriptor_zero_bytes':zero,'page_frame_bytes':n*page,'padding_bytes':pool-zero-n*page,'avoided_clear_bytes_if_validated':pool-zero,'avoided_clear_fraction':1-zero/pool,'scope':'static layout arithmetic for canonical Wasm32 16MiB pool, 16KiB pages; not observed runtime byte counters or speedup'}
assert zero==233856 and n==1008
(E/'layout.json').write_text(json.dumps(layout,indent=2)+'\n');(E/'patch-application.json').write_text(json.dumps(patches,indent=2)+'\n');(E/'generated-identity.json').write_text(json.dumps({'guest_sha256':prov['guest_sha256'],'file':rel,'sha256':prov['files_sha256'][rel]},indent=2)+'\n')
print('PASS pinned source hashes, selected canonical patches, zero contract anchors and static layout')
print(json.dumps(layout,indent=2))
