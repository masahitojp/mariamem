from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit

def out(args,**kw):return subprocess.check_output(args,text=True,**kw).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=json.loads((H/'plan.json').read_text());head=out(['git','rev-parse','HEAD'],cwd=S)
require_commit(S,head);require_commit(S,p['source_commit']);assert not out(['git','status','--porcelain'],cwd=S)
assert all(n.startswith('benchmarks/shopforkstages/') for n in out(['git','diff','--name-only',p['source_commit'],head],cwd=S).splitlines())
sdk=dict(os.environ,GOTOOLCHAIN=p['go']);go=str(Path(out(['go','env','GOROOT'],env=sdk))/'bin/go');cache=Path(out(['go','env','GOMODCACHE'],env=sdk))/'cache/download'
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_'))};env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',CGO_ENABLED='0',GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='4',GOMEMLIMIT='3GiB',GOGC='50',GOPROXY=cache.as_uri()+',https://proxy.golang.org',GOSUMDB='sum.golang.org')
version=out([go,'version'],env=env);assert version=='go version '+p['go']+' darwin/arm64'
module=T/'runner';module.mkdir()
for name in ['internal','maria']:shutil.copytree(H/name,module/name)
(module/'go.mod').write_text((H/'go.mod').read_text().replace('replace github.com/masahitojp/mariamem => ../..','replace github.com/masahitojp/mariamem => '+str(S)))
shutil.copyfile(H/'go.sum',module/'go.sum')
overlay=T/'overlay';subprocess.run([sys.executable,str(H/'overlay.py'),str(S),str(overlay)],check=True)
with (E/'observer-unit.txt').open('w') as log:subprocess.run([go,'test','-overlay',str(overlay/'overlay.json'),'-count=1','./internal/timing'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print('BUILD current Fork-stage on/off binary',flush=True)
with (T/'build.txt').open('w') as log:subprocess.run([go,'test','-overlay',str(overlay/'overlay.json'),'-c','-trimpath','-p','1','-buildvcs=false','-mod=readonly','-o',str(T/'bin-current'),'./maria/store'],cwd=module,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
shutil.copyfile(overlay/'bindings.json',E/'bindings.json')
inputs=dict(function_map_proof=json.loads((E/'function-map-proof.json').read_text()),bindings=json.loads((overlay/'bindings.json').read_text()),overlay_hashes=json.loads((overlay/'hashes.json').read_text()),harness_source_commit=head,product_source_commit=p['source_commit'],go=version,binary_sha256=sha(T/'bin-current'),build_info=out([go,'version','-m',str(T/'bin-current')]).replace(str(W),'<WORKSPACE>'),module_sha256=sha(module/'go.mod'),harness_files={str(f.relative_to(H)):sha(f) for f in H.rglob('*') if f.is_file()},product_inputs={n:sha(S/n) for n in ['guest/input.json','release/generated-go-inputs.json','internal/generatedgo/provenance.json','go.mod','go.sum']})
(E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');assert not out(['git','status','--porcelain'],cwd=S);print('BUILT',flush=True)
