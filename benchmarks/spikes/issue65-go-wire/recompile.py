import os,sys,json,subprocess,hashlib
from pathlib import Path
w=Path('.').resolve();repo=w/'worktree';sys.path.insert(0,str(repo/'scripts'));from build_feedback import go_environment
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w);env=go_environment({**{k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')},'GOTOOLCHAIN':'go1.26.10','GOWORK':'off','GOENV':'off','CGO_ENABLED':'0','GOMAXPROCS':'2','GOGC':'50'})
product=w/'temp/host/product';binary=w/'temp/host/wire.test';subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/issue65-wire'],cwd=product,env=env,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
(w/('evidence/host-build-'+sys.argv[1]+'.json')).write_text(json.dumps({'scope':'isolated experimental host iteration','binary_sha256':sha(binary),'source_inventory':{str(p.relative_to(product)):sha(p) for p in product.rglob('*') if p.is_file()},'guest_sha256':json.loads((w/'temp/artifact/guest.json').read_text())['guest_sha256'],'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2)+'\n')
