import os,sys,subprocess,json,re,hashlib
from pathlib import Path
w=Path(__file__).resolve().parents[1];origin=w/'worktree';root=w.parents[2];sys.path.insert(0,str(root/'scripts'))
import dev_guest,runtime_thread_lifetime as b,runtime_atomic_loads as a,runtime_memfs as m
r=json.loads((w/'evidence/guest.json').read_text());t=w/'temp/translation';dev_guest.verify_guest(origin,next((w/'temp/ci').glob('prepared-p1-unqualified-guest-*')));dev_guest.verify_translation(origin,t,r['guest_sha256'])
identity=json.loads((root/'tests/fixtures/prepared-p2-binding/identity.json').read_text());assert identity['guest_sha256']==b.GUEST_SHA256==r['guest_sha256']
for name,(fn,h) in b.FUNCTIONS.items():
 body=b.function((t/'module/generated'/name.removeprefix('code/')).read_text(),fn)
 assert body==(root/'tests/fixtures/prepared-p2-binding'/(fn+'.txt')).read_text()
 assert hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest()==h
pin=identity['memory_init'];body=b.function((t/'module/generated'/pin['file'].removeprefix('code/')).read_text(),pin['function']);assert body==(root/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text();assert hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest()==pin['normalized_sha256']
content=(t/'module/generated/data.bin').read_bytes();assert hashlib.sha256(content).hexdigest()==identity['data_sha256']
for seg in identity['data_segments']:assert hashlib.sha256(content[seg['start']:seg['end']]).hexdigest()==seg['sha256']
env={k:v for k,v in os.environ.items() if k not in ('GOPATH','GOCACHE','GOMODCACHE','GOROOT','MARIAMEM_DEV_WORKSPACE')};env.update(GOTOOLCHAIN='go1.26.8',GOENV='off',GOWORK='off');assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.26.8 darwin/arm64'
guest=next((w/'temp/ci').glob('prepared-p1-unqualified-guest-*'))/'mariamem.wasm'
with (w/'evidence/adapter.txt').open('w') as log:subprocess.run([sys.executable,str(origin/'benchmarks/spikes/generated-go-integration/setup_candidate.py'),'--source-only','--source-module',str(t/'module'),'--guest',str(guest),'--input-manifest',str(t/'input-manifest.json'),'--output',str(w/'temp/candidate')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
base=(w/'temp/candidate/module/generated/base/base.go').read_text().replace('example.com/mariamem-spike/generated','github.com/masahitojp/mariamem/internal/generatedgo/code');b.apply('code/base/base.go',m.apply(a.apply(base)))
for name in b.FUNCTIONS:b.apply(name,(w/'temp/candidate/module/generated'/name.removeprefix('code/')).read_text().replace('example.com/mariamem-spike/generated','github.com/masahitojp/mariamem/internal/generatedgo/code'))
b.validate_inputs(r['guest_sha256'],set('generated/'+n for n in json.loads((t/'input-manifest.json').read_text())['files_sha256']))
(w/'evidence/owner-checks.json').write_text(json.dumps({'complete_functions_data_TLS_init':'PASS','formal_source_adapter':'PASS','pure_atomic_memfs_lifetime_transforms':'PASS','single_guest_input_guard':'PASS','installed_runtime':'NOT RUN'},indent=2)+'\n')
print('PASS: formal source adapter and exact new binding/pure owner transforms')
