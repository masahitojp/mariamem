"""Static cross-check of pinned upstream, guest shim and prior observed ranges.
No guest executes. Download the four exact upstream paths listed in the report
into --upstream; apply only the two named common-portability patch sections to a
copy at --patched. Optional --check compares with the saved read-only receipt.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PRODUCT='b3b3b46a8807482ad3f96725af86e031fe369b01'
TRACE='d6e9249906b38ed1cc842865fda4b18364bd26c8'
UPSTREAM='83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e'
def blob(ref,name):return subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
def collect(upstream,patched):
 sys.path.insert(0,str(ROOT/'scripts'))
 from git_identity import require_commit,ReleasePin,verify_release_pin
 for c in [PRODUCT,TRACE]:require_commit(ROOT,c)
 verify_release_pin(ROOT,ReleasePin('v0.6.0','b57183b08d48884840111e8b53daa500734337f0',PRODUCT))
 inp=json.loads(blob(PRODUCT,'guest/input.json'));assert inp['source_commit']==UPSTREAM
 patch=inp['patches'][0];assert patch['file']=='guest/patches/common-portability.patch'
 assert sha(blob(PRODUCT,patch['file']))==patch['sha256']
 paths=['storage/innobase/buf/buf0buf.cc','storage/innobase/include/buf0buf.h','mysys/my_largepage.c','mysys/my_virtual_mem.c'];files={}
 for n in paths:
  data=(upstream/n).read_bytes();files[n]={'sha256':sha(data),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'url':'https://github.com/MariaDB/server/blob/'+UPSTREAM+'/'+n}
 assert files[paths[0]]['git_blob_sha1']=='45b40a7e68d3a086a359a7b7bf48c9540e7ae32a'
 for n in paths[2:]:
  assert files[n]['sha256']==patch['before_sha256'][n]
  after=sha((patched/n).read_bytes());assert after==patch['after_sha256'][n];files[n]['patched_sha256']=after
 buf=(upstream/paths[0]).read_text();header=(upstream/paths[1]).read_text()
 assert 'sizeof(size_t) < 8 ? 2 << 20 : 8 << 20' in header
 a=buf.index('bool buf_pool_t::create()');b=buf.index('void buf_pool_t::close()',a);create=buf[a:b]
 reserve=create.index('memory_unaligned= my_virtual_mem_reserve(&size)')
 retry=create.index('if (size < size_in_bytes_max + alignment_waste)',reserve)
 release=create.index('my_virtual_mem_release(memory_unaligned, size)',retry)
 jump=create.index('goto retry;',release)
 commit=create.index('my_virtual_mem_commit(memory, actual_size)',jump)
 assert reserve<retry<release<jump<commit
 native_reserve=(upstream/'mysys/my_virtual_mem.c').read_text();assert 'return my_large_virtual_alloc(size);' in native_reserve
 shim=(patched/'mysys/my_largepage.c').read_text();start=shim.index('char *my_large_virtual_alloc');end=shim.index('if (my_use_large_pages)',start);wasm=shim[start:end]
 assert 'posix_memalign(&p, 4096, *size)' in wasm and 'memset(p, 0, *size)' in wasm
 v=(patched/'mysys/my_virtual_mem.c').read_text();start=v.index('void my_virtual_mem_release');assert 'free(ptr);' in v[start:start+220]
 # Decode only the existing generated constant data; never inspect live memory.
 generated=blob(PRODUCT,'internal/generatedgo/code/generated.go').decode();literal=generated.split('var wasm2goData_data_bin = []byte("',1)[1].split('")',1)[0];data=bytes.fromhex(literal.replace('\\x',''));assert len(data)==6856219
 strings={}
 for addr in [8570708,8570851]:
  offset=addr-8388608;strings[str(addr)]=data[offset:data.index(0,offset)].decode()
  assert strings[str(addr)] in buf.replace('"\n                        "','')
 go=blob(PRODUCT,'internal/generatedgo/code/p0/p0_pure.go').decode()
 start=go.index('L522:',go.index('func Fn18568('));end=go.index('L539:',start);fragment=go[start:end]
 for expected in ['Fn239(m, v2919+int32(12), int32(4096), v2928)','base.MemoryFill(m, v2934, int32(0), v2933)','Fn153(m, v2939)','v2882 = v2968 - v2970&int32(2097151) + int32(2097152)']:
  assert expected in fragment
 prefix='benchmarks/zerofill/results/'
 manifest=json.loads(blob(TRACE,prefix+'SHA256SUMS.json'));obsbytes=blob(TRACE,prefix+'observations.json');assert sha(obsbytes)==manifest['observations.json'];obs=json.loads(obsbytes)
 samples=[];extent=2<<20
 for name,result in obs['results'].items():
  if not result['observed']:continue
  assert result['success'] and result['cleanup']
  for phase in [1,4]:
   es=[e for e in result['large_zero_events'] if e['phase']==phase and e['bytes'] in [16777216,18567168] and any('Fn18568' in f['function'] for f in e['stack'])]
   assert len(es)==2
   first,second=es;assert first['bytes']==16<<20 and first['dst']==second['dst']
   waste=(-first['dst'])&(extent-1);assert waste>0 and first['bytes']+waste==second['bytes']
   assert second['bytes']-waste==16<<20
   samples.append(dict(report=name,phase=phase,address=first['dst'],first_size=first['bytes'],address_mod_extent=first['dst']%extent,alignment_waste=waste,retry_size=second['bytes'],usable_start=first['dst']+waste,usable_bytes=second['bytes']-waste))
 assert len(samples)==6
 return dict(result='STATIC_CORRESPONDENCE_CONFIRMED',product_source_commit=PRODUCT,trace_source_commit=TRACE,upstream_source_commit=UPSTREAM,guest_sha256=json.loads(blob(PRODUCT,'internal/generatedgo/provenance.json'))['guest_sha256'],patch_sha256=patch['sha256'],upstream_files=files,generated_sources_sha256={n:sha(blob(PRODUCT,n)) for n in ['internal/generatedgo/code/generated.go','internal/generatedgo/code/p0/p0_pure.go']},generated_retry_fragment_sha256=sha(fragment.encode()),decoded_log_strings=strings,samples=samples,limits='No new runtime execution or exact symbolmap; correspondence uses two embedded log strings, matching control flow/constants, patched source hashes and all six prior observed sizes. Performance savings and replacement allocation behavior unmeasured.')
def check_receipt(path):
 for name,h in json.loads((path.parent/'SHA256SUMS.json').read_text()).items():assert sha((path.parent/name).read_bytes())==h
 d=json.loads(path.read_text());assert d['result']=='STATIC_CORRESPONDENCE_CONFIRMED' and len(d['samples'])==6
 for row in d['samples']:
  extent=2<<20;assert row['first_size']==16<<20
  assert row['alignment_waste']==(-row['address'])&(extent-1)
  assert row['alignment_waste']>0 and row['first_size']+row['alignment_waste']==row['retry_size']
  assert row['usable_start']==row['address']+row['alignment_waste'] and row['usable_start']%extent==0
  assert row['usable_bytes']==row['retry_size']-row['alignment_waste']==16<<20
 print('PASS: saved receipt hashes and six alignment calculations; source re-fetch not performed')
def main():
 p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path);p.add_argument('--patched',type=Path);p.add_argument('--output',type=Path,default=Path(__file__).parent/'results/correspondence.json');p.add_argument('--check',action='store_true');p.add_argument('--receipt-only',action='store_true');a=p.parse_args()
 if a.receipt_only:check_receipt(a.output);return
 assert a.upstream and a.patched
 result=json.dumps(collect(a.upstream,a.patched),indent=2)+'\n'
 if a.check:assert a.output.read_text()==result;print('PASS: source correspondence and six alignment retries; read-only')
 else:a.output.write_text(result);print('PASS: source correspondence and six alignment retries')
if __name__=='__main__':main()
