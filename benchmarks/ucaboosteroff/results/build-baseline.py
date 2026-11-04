import os,subprocess,json,hashlib,sys
from pathlib import Path
w=Path(__file__).resolve().parents[1];s=w/'temp/source';e=w/'evidence';t=w/'temp'
sys.path.insert(0,str(s/'scripts'));import git_identity
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip();git_identity.require_commit(s,head);assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOTMPDIR=str(t/'go-tmp'));env.pop('MARIAMEM_DEV_WORKSPACE',None)
cmd=['/opt/homebrew/bin/go','build','-mod=readonly','-p','1','-trimpath','-buildvcs=true','-o',str(t/'baseline-host'),'./cmd/mariamem-host']
with (e/'baseline-build.log').open('w') as log:subprocess.run(cmd,cwd=s,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
os.environ['GOTOOLCHAIN']='go1.26.10';stamp=git_identity.verify_go_binary(s,t/'baseline-host',head,go='/opt/homebrew/bin/go',toolchain='go1.26.10')
(e/'baseline-binary.json').write_text(json.dumps({'source_commit':head,'behavior_source_commit':'bc00b8e66e5fd57bc9b2127001faf8e05952b417','inactive_experimental_patch':'canonical generated Go unchanged; this baseline does not compile the experimental guest','binary_sha256':hashlib.sha256((t/'baseline-host').read_bytes()).hexdigest(),'build_info':stamp},indent=2)+'\n')
print('baseline host build PASS')
