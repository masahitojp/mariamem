from pathlib import Path
import sys,subprocess,os,json
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp';sys.path.insert(0,str(W/'scripts'))
from build_generated_guest import download
from dev_guest import verify_guest
verify_guest(W,T/'guest');out=T/'preflight';out.mkdir(exist_ok=True);tools=json.loads((W/'release/generated-go-toolchain.json').read_text());converter=download(tools['archives']['converter'],out/'downloads');env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'));guest=json.loads((T/'guest/guest.json').read_text())['guest_sha256'];spike=W/'benchmarks/spikes/generated-go-integration'
subprocess.run([sys.executable,str(spike/'translate_guest.py'),'--guest',str(T/'guest/mariamem.wasm'),'--guest-sha256',guest,'--converter-archive',str(converter),'--output',str(out/'translation')],env=env,check=True)
subprocess.run([sys.executable,str(spike/'setup_candidate.py'),'--source-only','--source-module',str(out/'translation/module'),'--guest',str(T/'guest/mariamem.wasm'),'--input-manifest',str(out/'translation/input-manifest.json'),'--output',str(out/'candidate')],env=env,check=True)
