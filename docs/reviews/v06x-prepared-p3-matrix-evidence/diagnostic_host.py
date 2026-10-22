import os,sys,subprocess,json,hashlib,shutil
from pathlib import Path
w=Path(__file__).resolve().parents[1];root=w.parents[2];out=w/'temp/runtime';product=out/'product'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((out/'development.json').read_text());oldrecordsha=sha(out/'development.json')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root).strip()
identity=json.loads(subprocess.check_output([sys.executable,str(root/'scripts/git_identity.py'),'inspect','HEAD'],cwd=root,text=True));assert identity['object_type']=='commit'
for name,h in base['host_source_inventory'].items():assert sha(product/name)==h,name
files=subprocess.check_output(['git','ls-files','-z'],cwd=root,text=True).split('\0');source={}
canonical=json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
for name in files:
 if not name:continue
 source[name]=sha(root/name)
 if name.startswith('internal/generatedgo/'):continue
 data=(root/name).read_bytes()
 if name=='internal/runtimekind/kind.go':
  old=('const GuestSHA256 = "'+canonical+'"').encode();new=('const GuestSHA256 = "'+base['guest_sha256']+'"').encode();assert data.count(old)==1;data=data.replace(old,new,1)
 target=product/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
for name,h in base['generated_inventory'].items():assert sha(product/'internal/generatedgo'/name)==h,name
for name,h in base['host_source_inventory'].items():
 if name.startswith(('guest/','scripts/','release/','benchmarks/spikes/wasm2go/')):assert source[name]==h,name
inputs={name:sha(product/name) for name in source if not name.startswith('internal/generatedgo/')}
env={k:v for k,v in os.environ.items() if k not in ('GOPATH','GOCACHE','GOMODCACHE','GOROOT','MARIAMEM_DEV_WORKSPACE')}
env.update(GOTOOLCHAIN='go1.26.8',GOENV='off',GOWORK='off',GOCACHE=str(w/'temp/gocache'),GOPATH=str(w/'temp/gopath'),GOMODCACHE=str(w/'temp/modcache'),GOTMPDIR=str(w/'temp'))
version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.26.8 darwin/arm64'
record={'contract':'diagnostic-handwritten-host-patch-v1','result':'PENDING','source_commit':identity['source_commit'],'guest_sha256':base['guest_sha256'],'baseline_development_record_sha256':oldrecordsha,'baseline_host_source_commit':base['host_source_identity']['commit'],'source_files_sha256':source,'host_inputs_sha256':inputs,'generated_inventory':base['generated_inventory'],'scope':'Current committed handwritten source plus unchanged formally installed generated tree and existing dev runtimekind SHA replacement; not a new formal origin receipt'}
(w/'evidence/patched-host-inputs.json').write_text(json.dumps(record,indent=2)+'\n')
binary=w/'temp/mariamem-p3-fixed-host'
with (w/'evidence/patched-build.txt').open('w') as f:subprocess.run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/mariamem-host'],cwd=product,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
info=json.loads(subprocess.check_output([str(binary),'--snapshot-info'],env=env,text=True));assert info['wasm_sha256']==base['guest_sha256']
with (w/'evidence/go-unit.txt').open('w') as f:subprocess.run(['go','test','-p','1','-count=1','./internal/mysqlwire','./internal/preparedproto','./internal/guest'],cwd=product,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
for name,h in inputs.items():assert sha(product/name)==h,name
for name,h in base['generated_inventory'].items():assert sha(product/'internal/generatedgo'/name)==h,name
assert sha(out/'development.json')==oldrecordsha
record.update(result='PASS',binary_sha256=sha(binary),binary_bytes=binary.stat().st_size,go=version,unit='PASS (non-race; fresh both-OS race CI still required)',snapshot_info=info)
(w/'evidence/patched-host-inputs.json').write_text(json.dumps(record,indent=2)+'\n');print('Diagnostic handwritten host build and3 package units PASS')
