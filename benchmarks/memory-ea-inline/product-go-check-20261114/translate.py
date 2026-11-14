from pathlib import Path
import sys,zipfile,json,subprocess,os
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
sys.path.insert(0,str(S/'scripts'))
from build_generated_guest import download
from common import digest
with zipfile.ZipFile(T/'guest.zip') as z: (T/'mariamem.wasm').write_bytes(z.read('mariamem.wasm'))
sha=digest(T/'mariamem.wasm');assert sha=='77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450'
a=download(json.loads((S/'release/generated-go-toolchain.json').read_text())['archives']['converter'],T/'downloads')
cmd=[sys.executable,str(S/'benchmarks/spikes/generated-go-integration/translate_guest.py'),'--guest',str(T/'mariamem.wasm'),'--guest-sha256',sha,'--converter-archive',str(a),'--output',str(T/'translation')]
with (E/'translation.log').open('w') as f: subprocess.run(cmd,env=dict(os.environ,GOTOOLCHAIN='go1.26.10'),stdout=f,stderr=f,check=True,timeout=1200)
print('TRANSLATION PASS',flush=True)
