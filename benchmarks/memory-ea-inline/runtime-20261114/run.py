from pathlib import Path
import sys,subprocess,json,os,zipfile,hashlib,shutil
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
def call(cmd,cwd=S,name='step',timeout=1200):
 with (E/(name+'.log')).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=timeout)
 print(name+' PASS',flush=True)
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
call(['gh','api','repos/masahitojp/mariamem/actions/artifacts/14103568702/zip'],name='unused') if False else None
with (T/'guest.zip').open('wb') as f:subprocess.run(['gh','api','repos/masahitojp/mariamem/actions/artifacts/14103568702/zip'],stdout=f,check=True,timeout=180)
with zipfile.ZipFile(T/'guest.zip') as z:(T/'mariamem.wasm').write_bytes(z.read('mariamem.wasm'))
sys.path.insert(0,str(S/'scripts'));from build_generated_guest import download
pin=json.loads((S/'release/generated-go-inputs.json').read_text());sha=hashlib.sha256((T/'mariamem.wasm').read_bytes()).hexdigest();assert sha==pin['guest_sha256']
a=download(json.loads((S/'release/generated-go-toolchain.json').read_text())['archives']['converter'],T/'downloads')
call([sys.executable,S/'benchmarks/spikes/generated-go-integration/translate_guest.py','--guest',T/'mariamem.wasm','--guest-sha256',sha,'--converter-archive',a,'--output',T/'translation'],name='translation')
call([sys.executable,S/'benchmarks/spikes/generated-go-integration/setup_candidate.py','--source-only','--source-module',T/'translation/module','--guest',T/'mariamem.wasm','--input-manifest',T/'translation/input-manifest.json','--output',T/'candidate'],name='adapter')
module=T/'candidate/module';manifest=S/'release/generated-go-inputs.json';original=manifest.read_bytes()
pin['candidate_files_sha256']={str(p.relative_to(module)):hashlib.sha256(p.read_bytes()).hexdigest() for suffix in ('*.go','*.s') for p in module.rglob(suffix)}
(E/'proposed-install-inputs.json').write_text(json.dumps(pin,indent=2));manifest.write_text(json.dumps(pin,indent=2))
try:call([sys.executable,S/'scripts/generate_runtime.py','--source-module',module,'--output',T/'installed'],name='installation')
finally:manifest.write_bytes(original)
(E/'installation-unqualified.json').write_text(json.dumps({'result':'UNQUALIFIED','note':'isolated proposed input inventory used for deterministic installer; not accepted canonical pins','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip(),'guest_sha256':sha}))
shutil.copy2(T/'translation/input-manifest.json',E/'translation-manifest.json');shutil.copy2(T/'installed/provenance.json',E/'installed-provenance.json')
changes=[]
for p in (T/'installed').rglob('*'):
 if p.is_file():
  rel=p.relative_to(T/'installed');q=S/'internal/generatedgo'/rel
  if not q.exists() or p.read_bytes()!=q.read_bytes():changes.append(str(rel))
(E/'installed-changes.json').write_text(json.dumps(changes,indent=2));print('CHANGES',changes,flush=True)
