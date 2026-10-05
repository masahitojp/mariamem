#!/usr/bin/env python3
"""Disposable correctness campaign; no mmap, benchmark or soak."""
import difflib,hashlib,json,os,resource,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from fixtures import build
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
T=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']);E=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
SHARED=Path('/Users/masahito/src/mysqlmem/publish/mariamem');CACHE=Path('/Users/masahito/src/mysqlmem/build/mariamem-cache')
GO='/Users/masahito/.go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin/go';GF=str(Path(GO).with_name('gofmt'))
env=dict(os.environ,GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',CGO_ENABLED='0',GOCACHE=str(SHARED/'build/gocache'),GOMODCACHE='/Users/masahito/.go/pkg/mod')
record={'released_base':'547fb1a6c01e5edb0daa27de273a2e94e66eb098','converter_commit':'ac98bcf00c17d8531f0c071a9836d0b50975e7ff','phases':[],'fixture_pass':False,'product_smoke':False,'mmap':False,'performance_measurement':False,'budgets':{'disk_gib':4,'free_disk_gib':16,'rss_gib':6,'physical_gib':8,'cpu_per_process_seconds':[180,200]}}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(E/'campaign.json').write_text(json.dumps(record,indent=2)+'\n')
def limits():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(180,200));resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
def run(name,cmd,cwd=ROOT,expect=0,timeout=600,extras=None):
 print('RUN',name,flush=True);start=time.monotonic();row={'name':name,'command':list(map(str,cmd)),'peak_rss_bytes':0,'peak_physical_bytes':0};record['phases'].append(row);save()
 with (E/(name+'.log')).open('wb') as log:
  p=subprocess.Popen(list(map(str,cmd)),cwd=cwd,env=dict(env,**(extras or {})),stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits)
  try:
   while p.poll() is None:
    if time.monotonic()-start>timeout:raise RuntimeError(name+' watchdog')
    if (T/'process-cost').exists():
     rows=subprocess.check_output(['ps','-A','-o','pid=,ppid='],text=True);pairs=[tuple(map(int,x.split())) for x in rows.splitlines() if len(x.split())==2];ids={p.pid}
     for _ in range(len(pairs)):
      n=len(ids);ids.update(a for a,b in pairs if b in ids)
      if n==len(ids):break
     counters=json.loads(subprocess.check_output([str(T/'process-cost'),*map(str,ids)],text=True));rss=sum(x.get('rss_bytes',0) for x in counters.values());phys=sum(x.get('primary_bytes',0) for x in counters.values());row['peak_rss_bytes']=max(row['peak_rss_bytes'],rss);row['peak_physical_bytes']=max(row['peak_physical_bytes'],phys)
     if rss>6*(1<<30) or phys>8*(1<<30):
      row.update(stop='memory budget',rss_bytes_at_stop=rss,physical_bytes_at_stop=phys);save();raise RuntimeError(name+' memory budget')
    time.sleep(.2)
  finally:
   if p.poll() is None:p.kill();p.wait()
 row.update(exit_code=p.returncode,elapsed_seconds=time.monotonic()-start);save();print('END',name,p.returncode,flush=True)
 if expect is not None and p.returncode!=expect:raise RuntimeError(name+' failed; evidence retained')
 return p.returncode
def campaign():
 save();run('build-counter',['cc','-O2',ROOT/'benchmarks/tools/process_cost.c','-o',T/'process-cost'])
 archive=CACHE/'wasm2go-fork.tar.gz';record['converter_archive_sha256']=digest(archive);assert record['converter_archive_sha256']=='1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f'
 container=T/'converter';container.mkdir()
 with tarfile.open(archive) as tar:tar.extractall(container,filter='data')
 source=next(container.iterdir())
 for patch in ['imported-memory.patch','import-function-index.patch','relaxed-madd.patch']:
  run('apply-'+patch,['git','apply','--unidiff-zero',ROOT/'benchmarks/spikes/wasm2go'/patch],cwd=source)
 run('build-baseline-converter',[GO,'build','-p','1','-trimpath','-o',T/'baseline-converter','./cmd/wasm2go'],cwd=source)
 old={str(p.relative_to(source)):p.read_text() for p in source.rglob('*.go')}
 run('apply-generic-rule',[sys.executable,HERE/'patch_converter.py',source])
 changed=[p for p in source.rglob('*.go') if old[str(p.relative_to(source))]!=p.read_text()]
 run('format-prototype',[GF,'-w',*changed],cwd=source)
 patch=''.join(''.join(difflib.unified_diff(old[str(p.relative_to(source))].splitlines(True),p.read_text().splitlines(True),fromfile='a/'+str(p.relative_to(source)),tofile='b/'+str(p.relative_to(source)))) for p in sorted(changed))
 (E/'generic-memory.patch').write_text(patch);record['prototype_files']=[str(p.relative_to(source)) for p in changed];record['prototype_patch_bytes']=len(patch.encode());save()
 run('build-checked-converter',[GO,'build','-p','1','-trimpath','-o',T/'checked-converter','./cmd/wasm2go'],cwd=source)
 f=T/'fixtures';record['fixture_case_count']=build(f);save()
 run('wasm-reference',['node',HERE/'reference.js',f/'contract.wasm',f/'matrix.json'])
 reference=[json.loads(l) for l in (E/'wasm-reference.log').read_text().splitlines() if l.startswith('{')]
 # Wasmer native reference on representative scalar/SIMD/atomic boundaries.
 wasmer=SHARED/'build/tools/wasmer/bin/wasmer';native=[]
 for op,addr,traps in [('l32o0',32,False),('s64o0',65535,True),('l32o4',-4,True),('vl128o0',65521,True),('vs128o0',32,False),('al32o0',1,True),('ar64o0',65536,True),('al32o4',-4,True)]:
  code=run('wasmer-'+op+'-'+str(addr),[wasmer,'run','--wasmer-dir',T/'wasmer-home','--cache-dir',T/'wasmer-cache','--invoke',op,f/'contract.wasm','--',str(addr)],expect=None,timeout=60)
  log=(E/('wasmer-'+op+'-'+str(addr)+'.log')).read_text();accepted=(code!=0 and ('out of bounds' in log.lower() or 'unaligned' in log.lower())) if traps else code==0
  native.append({'op':op,'addr':addr,'expected_trap':traps,'exit_code':code,'matches_reference':accepted})
 (E/'wasmer-reference.json').write_text(json.dumps(native,indent=2)+'\n');record['wasmer_reference_pass']=all(x['matches_reference'] for x in native);save()
 for mode in ['baseline','checked']:
  project=T/('fixture-'+mode);(project/'fixture').mkdir(parents=True);(project/'go.mod').write_text('module genericfixture\n\ngo 1.26.0\n');shutil.copyfile(HERE/'matrix.go.txt',project/'main.go')
  cmd=[T/(mode+'-converter'),'-pure','-i',f/'contract.wasm','-o',project/'fixture/fixture.go','-pkg','fixture','-import','genericfixture/fixture']
  if mode=='checked':cmd+=['-checked-memory']
  run('translate-'+mode,cmd)
  run('build-fixture-'+mode,[GO,'build','-p','1','-o',T/(mode+'-fixture'),'.'],cwd=project)
  run('fixture-'+mode,[T/(mode+'-fixture'),f/'matrix.json'],extras={'BASELINE_ONLY_SAFE':'1'} if mode=='baseline' else {})
  rows=[json.loads(l) for l in (E/('fixture-'+mode+'.log')).read_text().splitlines() if l.startswith('{')];index={(x['op'],x['addr'],x['grow']):x for x in reference};mismatch=[]
  for row in rows:
   want=index[row['op'],row['addr'],row['grow']]
   if any(row[k]!=want[k] for k in ['trap','value','before','after']):mismatch.append({'op':row['op'],'addr':row['addr'],'grow':row['grow'],'expected_trap':want['trap'],'actual_trap':row['trap']})
  record[mode+'_mismatches']=mismatch;record[mode+'_executed_cases']=len(rows);save()
  if mode=='checked':assert not mismatch
 record['fixture_pass']=True;save()
 # Pin full-guest input; regenerate generically, never patch a generated function.
 guest=Path('/Users/masahito/src/mysqlmem/build/mariamem-work/release-ci-migration/source/build/generated-release/mariamem.wasm');assert digest(guest)==json.loads((ROOT/'release/generated-go-inputs.json').read_text())['guest_sha256']
 record['guest_sha256']=digest(guest);save();generated=T/'guest-generated'
 run('regenerate-guest',[T/'checked-converter','-pure','-checked-memory','-i',guest,'-out-dir',generated,'-pkg','generated','-import','github.com/masahitojp/mariamem/internal/generatedgo/code'],timeout=600)
 product=T/'product';product.mkdir();tarfile_path=T/'product-source.tar'
 with tarfile_path.open('wb') as dest:subprocess.run(['git','archive','v0.4.1'],cwd=ROOT,stdout=dest,check=True)
 with tarfile.open(tarfile_path) as tar:tar.extractall(product,filter='data')
 tarfile_path.unlink()
 sys.path.insert(0,str(ROOT/'benchmarks/spikes/generated-go-integration'));from patch_memfs import apply
 assert digest(generated/'data.bin')==json.loads((ROOT/'release/generated-go-inputs.json').read_text())['data_sha256']
 for p in generated.rglob('*'):
  if p.suffix not in ('.go','.s'):continue
  text=p.read_text()
  if p.relative_to(generated).as_posix()=='base/base.go':text=apply(text)
  if p.name=='generated.go':
   data=(generated/'data.bin').read_bytes();text=text.replace('\t_ "embed"\n','').replace('//go:embed data.bin\nvar wasm2goData_data_bin []byte','var wasm2goData_data_bin = []byte("'+''.join('\\x%02x'%b for b in data)+'")')
  dest=product/'internal/generatedgo/code'/p.relative_to(generated);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 record['generated_inventory']={str(p.relative_to(generated)):digest(p) for p in generated.rglob('*') if p.is_file()};save()
 run('focused-runtime-race',[GO,'test','-race','-p','1','-count=1','./internal/generatedgo/code/base'],cwd=product,extras={'CGO_ENABLED':'1'})
 shutil.copyfile(HERE/'product_smoke_test.go.txt',product/'tests/godefault/generic_memory_smoke_test.go')
 run('product-smoke',[GO,'test','-p','1','-tags=integration','-v','-count=1','-run=TestGeneric','-timeout=120s','./tests/godefault'],cwd=product,timeout=600)
 record['product_smoke']=True;record['finished']=True;save()

if __name__=='__main__':campaign()
