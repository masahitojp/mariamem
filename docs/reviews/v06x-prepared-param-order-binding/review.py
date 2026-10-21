import hashlib,json,re,sys,subprocess,os
from pathlib import Path
w=Path(__file__).resolve().parents[1]; root=w/'worktree';sys.path.insert(0,str(root/'scripts'))
import dev_guest,runtime_thread_lifetime as b,runtime_atomic_loads as a,runtime_memfs as m
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
normal=lambda s:hashlib.sha256(re.sub(r'\s+','',s).encode()).hexdigest()
t=w/'temp/translation';raw=dev_guest.verify_translation(root,t,json.loads((w/'evidence/guest.json').read_text())['guest_sha256'])
old=json.loads((root/'docs/reviews/v06x-prepared-p2-repair-binding/translation-inputs.json').read_text())
for key in ('converter_commit','converter_archive_sha256','patched_converter_sha256','patches_sha256'):assert raw[key]==old[key],key
comparison={n:{'before':old['files_sha256'].get(n),'after':v,'changed':old['files_sha256'].get(n)!=v} for n,v in raw['files_sha256'].items()}
assert set(raw['files_sha256'])==set(old['files_sha256'])
(w/'evidence/raw-inventory-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
ident=json.loads((root/'tests/fixtures/prepared-p2-binding/identity.json').read_text()); review={}
for name,(fn,expected) in b.FUNCTIONS.items():
 body=b.function((t/'module/generated'/name.removeprefix('code/')).read_text(),fn)
 (w/'evidence'/(fn+'.txt')).write_text(body)
 fixture=(root/'tests/fixtures/prepared-p2-binding'/(fn+'.txt')).read_text()
 review[name]={'function':fn,'normalized_sha256':normal(body),'byte_identical':body==fixture}
 assert body==fixture and normal(body)==expected,name
pin=ident['memory_init'];body=b.function((t/'module/generated'/pin['file'].removeprefix('code/')).read_text(),pin['function'])
(w/'evidence/memory-init.txt').write_text(body)
assert normal(body)==pin['normalized_sha256'] and body==(root/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text()
data=t/'module/generated/data.bin';assert sha(data)==ident['data_sha256'];content=data.read_bytes()
for s in ident['data_segments']:assert hashlib.sha256(content[s['start']:s['end']]).hexdigest()==s['sha256']
generated=(t/'module/generated/generated.go').read_text(); declaration='m.DataSegs = [][]byte{'+', '.join(f'wasm2goData_data_bin[{s["start"]}:{s["end"]}]' for s in ident['data_segments'])+'}'
assert declaration in generated
(w/'evidence/binding-review.json').write_text(json.dumps({'functions':review,'data_sha256':sha(data),'data_segments':ident['data_segments'],'memory_init':pin,'all_exact_preimages_match':True},indent=2)+'\n')
env={k:v for k,v in os.environ.items() if k not in ('GOPATH','GOCACHE','GOMODCACHE','GOROOT','MARIAMEM_DEV_WORKSPACE')};env.update(PATH='/Users/masahito/.go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin:'+env['PATH'],GOTOOLCHAIN='go1.26.8',GOENV='off',GOWORK='off')
guest=next((w/'temp/ci').glob('prepared-p1-unqualified-guest-*'))/'mariamem.wasm'
with (w/'evidence/adapter.txt').open('w') as log:subprocess.run([sys.executable,str(root/'benchmarks/spikes/generated-go-integration/setup_candidate.py'),'--source-only','--source-module',str(t/'module'),'--guest',str(guest),'--input-manifest',str(t/'input-manifest.json'),'--output',str(w/'temp/candidate')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
base=(w/'temp/candidate/module/generated/base/base.go').read_text().replace('example.com/mariamem-spike/generated','github.com/masahitojp/mariamem/internal/generatedgo/code')
base=b.apply('code/base/base.go',m.apply(a.apply(base)))
for name in b.FUNCTIONS:b.apply(name,(w/'temp/candidate/module/generated'/name.removeprefix('code/')).read_text().replace('example.com/mariamem-spike/generated','github.com/masahitojp/mariamem/internal/generatedgo/code'))
(w/'evidence/owner-checks.json').write_text(json.dumps({'adapter':'PASS','atomic_memfs_lifetime_pure_transforms':'PASS','installed_runtime':'NOT RUN'},indent=2)+'\n')
print('PASS: converter, full function/data/TLS/initialization preimages and source adapter')
