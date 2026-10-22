import os,sys,json,subprocess,hashlib
from pathlib import Path
w=Path(__file__).resolve().parents[1];root=w/'worktree';sys.path.insert(0,str(root/'scripts'))
import dev_guest
source=subprocess.check_output([sys.executable,str(root/'scripts/git_identity.py'),'inspect','HEAD'],cwd=root,text=True)
(w/'evidence/source-identity.json').write_text(source)
guest=next((w/'temp/ci').glob('prepared-p1-unqualified-guest-*'))
r=dev_guest.verify_guest(root,guest)
assert r['prepared_source']['experimental_prepared_patch']==json.loads((root/'guest/prepared_source_patch.json').read_text())
(w/'evidence/guest.json').write_text(json.dumps(r,indent=2)+'\n')
print('VERIFIED GUEST',r['guest_sha256'],r['guest_bytes'],flush=True)
env={k:v for k,v in os.environ.items() if k not in ('GOPATH','GOCACHE','GOMODCACHE','GOROOT')}
env.update(GOTOOLCHAIN='go1.26.8',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',MARIAMEM_DEV_WORKSPACE=str(w))
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.26.8 darwin/arm64'
with (w/'evidence/translation.txt').open('w') as log:
 subprocess.run([sys.executable,str(root/'benchmarks/spikes/generated-go-integration/translate_guest.py'),'--guest',str(guest/'mariamem.wasm'),'--guest-sha256',r['guest_sha256'],'--converter-archive',str(w/'temp/wasm2go.tar.gz'),'--output',str(w/'temp/translation')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
raw=dev_guest.verify_translation(root,w/'temp/translation',r['guest_sha256'])
(w/'evidence/translation-inputs.json').write_text(json.dumps(raw,indent=2)+'\n')
print('TRANSLATION VERIFIED',flush=True)
