from support import *
import tarfile,urllib.request,hashlib,runpy
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
tools=json.loads((R/'release/generated-go-toolchain.json').read_text());pin=tools['archives']['converter'];archive=T/'converter.tar.gz'
with urllib.request.urlopen(pin['url'],timeout=60) as f:archive.write_bytes(f.read())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==pin['sha256']
src=T/'converter-source';src.mkdir()
with tarfile.open(archive) as tar:tar.extractall(src,filter='data')
src=next(src.iterdir())
for name in ['imported-memory.patch','import-function-index.patch','relaxed-madd.patch','pure-memory32.patch','linear-memory-owner.patch']:
 run('patch-'+name,['git','apply','--unidiff-zero',R/'benchmarks/spikes/wasm2go'/name],cwd=src)
run('converter-unit',['go','test','-p','1','-run=^(TestMemoryAccessWidths|TestTrappingLoadIsObservable|TestPureMemory32RetainsIndividualStores|TestDCE.*)$','./internal/codegen','./internal/ssa','./internal/ssa/pass'],cwd=src)
run('converter-build',['go','build','-p','1','-trimpath','-o',T/'converter','./cmd/wasm2go'],cwd=src)
run('fixture-heap',[sys.executable,R/'benchmarks/spikes/memory-candidate/check_fixture.py','--converter',T/'converter','--output',T/'fixture-heap'])
os.environ['MARIAMEM_PREPARED_TEMP']=str(T)
runpy.run_path(str(R/'benchmarks/spikes/mmap-integration/accept.py'),run_name='__main__')
runpy.run_path(str(R/'benchmarks/spikes/mmap-integration/products.py'),run_name='__main__')
runpy.run_path(str(R/'benchmarks/spikes/mmap-integration/measure.py'),run_name='__main__')
