from pathlib import Path
import os,subprocess,json,sys,time
w=Path(__file__).resolve().parents[1];t=w/'temp';s=t/'source';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));import dev_guest
j=dev_guest.verify_guest(s,t/'dev-guest');assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOTMPDIR=str(t/'go-tmp'),MARIAMEM_PHASE_TRACE=str(e/'abi-preflight-phases.jsonl'),PYTHONPYCACHEPREFIX=str(t/'pycache'));env.pop('MARIAMEM_DEV_WORKSPACE',None)
p=t/'abi-preflight';p.mkdir();spike=s/'benchmarks/spikes/generated-go-integration';commands=[[str(t/'venv/bin/python'),str(spike/'translate_guest.py'),'--guest',str(t/'dev-guest/mariamem.wasm'),'--guest-sha256',j['guest_sha256'],'--converter-archive',str(t/'stage-build/downloads/wasm2go-upstream.tar.gz'),'--output',str(p/'translation')],[str(t/'venv/bin/python'),str(spike/'setup_candidate.py'),'--source-only','--source-module',str(p/'translation/module'),'--guest',str(t/'dev-guest/mariamem.wasm'),'--input-manifest',str(p/'translation/input-manifest.json'),'--output',str(p/'candidate')]]
(e/'abi-preflight-command.json').write_text(json.dumps(commands,indent=2)+'\n');start=time.time()
with (e/'abi-preflight.log').open('w') as log:
 for cmd in commands:subprocess.run(cmd,cwd=s,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
(e/'abi-preflight-exit.json').write_text(json.dumps({'result':'RAW_TRANSLATION_ONLY','wall_seconds':time.time()-start})+'\n');print('raw translation and source adapter complete; ABI proof next')
