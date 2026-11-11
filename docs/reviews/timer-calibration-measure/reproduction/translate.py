from pathlib import Path
import os,sys,subprocess,json
W=Path(__file__).resolve().parents[1]; S=W/'worktree'; T=W/'temp'
sys.path.insert(0,str(S/'scripts'))
from dev_guest import verify_guest, verify_translation
from build_generated_guest import download
from build_feedback import go_environment
r=verify_guest(S,T/'guest')
environment=dict(os.environ,MARIAMEM_DEV_WORKSPACE=str(W),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off')
for key in ('GOCACHE','GOMODCACHE','GOPATH'): environment.pop(key,None)
env=go_environment(environment)
converter=download(json.loads((S/'release/generated-go-toolchain.json').read_text())['archives']['converter'],T/'downloads')
spike=S/'benchmarks/spikes/generated-go-integration'
subprocess.run([sys.executable,str(spike/'translate_guest.py'),'--guest',str(T/'guest/mariamem.wasm'),'--guest-sha256',r['guest_sha256'],'--converter-archive',str(converter),'--output',str(T/'inspect-translation')],check=True,env=env)
verify_translation(S,T/'inspect-translation',r['guest_sha256'])
subprocess.run([sys.executable,str(spike/'setup_candidate.py'),'--source-only','--source-module',str(T/'inspect-translation/module'),'--guest',str(T/'guest/mariamem.wasm'),'--input-manifest',str(T/'inspect-translation/input-manifest.json'),'--output',str(T/'inspect-candidate')],check=True,env=env)
print('translation and source adapter verified',flush=True)
