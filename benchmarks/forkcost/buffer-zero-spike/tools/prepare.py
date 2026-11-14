from pathlib import Path
import urllib.request,hashlib,subprocess,re,difflib,json
E=Path(__file__).resolve().parent;W=E.parent/'worktree';T=E.parent/'temp';S=T/'patch-source';f=S/'storage/innobase/buf/buf0buf.cc';f.parent.mkdir(parents=True,exist_ok=True)
u='https://raw.githubusercontent.com/MariaDB/server/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc';b=urllib.request.urlopen(u,timeout=60).read();assert hashlib.sha256(b).hexdigest()=='56c39160b207e16482d0f501e7b58b48708848caf74567cf2fa6ae83a3fddfb1';f.write_bytes(b)
p=(W/'guest/patches/12.3.3-buffer-alignment.patch').read_text();parts=re.split(r'(?m)(?=^--- )',p);p=''.join(x for x in parts if x.startswith('--- a/storage/innobase/buf/buf0buf.cc\n'));(T/'alignment.patch').write_text(p);subprocess.run(['patch','-p1','--batch','-i',str(T/'alignment.patch')],cwd=S,check=True)
a=f.read_text();z=a
old='''bool buf_pool_t::create() noexcept
{
'''
new=old+'''#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  /* Disposable experiment only: baseline, metadata, poison, bad-descriptors. */
  const char *bp_mode_env= getenv("MARIAMEM_BP_ZERO_MODE_INTERNAL");
  const int bp_mode= !bp_mode_env || !strcmp(bp_mode_env, "baseline") ? 0 :
    !strcmp(bp_mode_env, "metadata") ? 1 :
    !strcmp(bp_mode_env, "poison") ? 2 :
    !strcmp(bp_mode_env, "bad-descriptors") ? 3 : -1;
  size_t bp_descriptor_bytes= 0, bp_frames= 0;
  if (bp_mode < 0) abort();
#endif
'''
assert z.count(old)==1;z=z.replace(old,new)
old='''    memory_unaligned= my_large_virtual_alloc_aligned(
        &size, innodb_buffer_pool_extent_size);'''
new='''    if (!bp_mode)
      memory_unaligned= my_large_virtual_alloc_aligned(
          &size, innodb_buffer_pool_extent_size);
    else
    {
      void *p= nullptr;
      memory_unaligned= posix_memalign(&p, innodb_buffer_pool_extent_size, size)
        ? nullptr : static_cast<char*>(p);
      if (memory_unaligned && bp_mode >= 2)
        memset(memory_unaligned, 0xa5, size);
    }'''
assert z.count(old)==1;z=z.replace(old,new)
old='''    MEM_MAKE_DEFINED(block, (extent_end - block) * sizeof *block);
    for (byte *frame'''
new='''#if defined(__EMSCRIPTEN__) || defined(__wasi__)
    if (bp_mode)
    {
      const size_t descriptor_bytes= (extent_end - block) * sizeof *block;
      if (bp_mode != 3)
        memset((void*) block, 0, descriptor_bytes);
      if (bp_mode >= 2)
      {
        for (size_t i= 0; i < descriptor_bytes; ++i)
          if (reinterpret_cast<const byte*>(block)[i] != 0)
          {
            fprintf(stderr, "BP_ZERO_REJECT nonzero_descriptor\\n");
            abort();
          }
        bp_descriptor_bytes+= descriptor_bytes;
      }
    }
#endif
    MEM_MAKE_DEFINED(block, (extent_end - block) * sizeof *block);
    for (byte *frame'''
assert z.count(old)==1;z=z.replace(old,new)
old='''      ut_ad(!memcmp(block, field_ref_zero, sizeof *block));
      block->page.frame= frame;'''
new='''#if defined(__EMSCRIPTEN__) || defined(__wasi__)
      if (bp_mode == 2)
      {
        for (size_t i= 0; i < srv_page_size; ++i)
          if (frame[i] != 0xa5) abort();
        ++bp_frames;
      }
#endif
      ut_ad(!memcmp(block, field_ref_zero, sizeof *block));
      block->page.frame= frame;'''
assert z.count(old)==1;z=z.replace(old,new)
old='''  UT_LIST_INIT(withdrawn, &buf_page_t::list);'''
new='''#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  if (bp_mode == 2)
    fprintf(stderr, "BP_ZERO_WITNESS pool=%zu descriptor=%zu frames=%zu page=%zu aligned=%u\\n",
            actual_size, bp_descriptor_bytes, bp_frames, size_t(srv_page_size),
            unsigned(!(size_t(memory) & (innodb_buffer_pool_extent_size - 1))));
#endif

'''+old
assert z.count(old)==1;z=z.replace(old,new)
patch=''.join(difflib.unified_diff(a.splitlines(True),z.splitlines(True),fromfile='a/storage/innobase/buf/buf0buf.cc',tofile='b/storage/innobase/buf/buf0buf.cc'));(W/'guest/experimental.patch').write_text(patch)
f=W/'internal/generatedgo/runtime_instance.go';s=f.read_text();assert s.count('"io"')==1;s=s.replace('"io"','"io"\n "os"');anchor='values := []string{"MARIAMEM_BOOT_MODE=" + mode}';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n if v, ok := os.LookupEnv("MARIAMEM_BP_ZERO_MODE_INTERNAL"); ok { values = append(values, "MARIAMEM_BP_ZERO_MODE_INTERNAL="+v) }');f.write_text(s)
subprocess.run(['gofmt','-w',str(f)],check=True)
(E/'patch-input.json').write_text(json.dumps({'url':u,'before_sha256':hashlib.sha256(b).hexdigest(),'experimental_patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'scope':'buffer pool create only; common zero-filled allocator unchanged'},indent=2)+'\n')
for n in ['root','work','build','gocache','modcache']:(T/n).mkdir(exist_ok=True)
(T/'build/go.mod').write_bytes((W/'build/go.mod').read_bytes())
