"""Bounded refresh of the pinned previous P4/P8 TCP campaign."""
from pathlib import Path
import os,subprocess,sys,json,hashlib,time
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';C=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(C/'scripts'))
from git_identity import inspect_ref,require_commit,ReleasePin,verify_release_pin
started=time.monotonic()
def run(args,cwd=C,log='setup.txt',timeout=1200):
 print('RUN',log,flush=True)
 with (E/log).open('w') as f:subprocess.run(list(map(str,args)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
harness=inspect_ref(C,'HEAD');require_commit(C,harness.source_commit);assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
(T/'temp').mkdir()
for label,ref,path in [('harness',harness.source_commit,T/'harness'),('product','6e29c1cd125aa95f564969b905cbff462d4f0e74',T/'temp/product')]:
 run(['git','clone','--shared','--no-checkout',C,path],log='clone-'+label+'.txt');run(['git','checkout','--detach',ref],cwd=path,log='checkout-'+label+'.txt');require_commit(path,ref);assert not subprocess.check_output(['git','status','--porcelain'],cwd=path)
pg=T/'temp/pgmem';run(['git','clone','--depth','1','--branch','v1.18.2','https://github.com/shibukawa/pgmem.git',pg],log='clone-pgmem.txt')
pin=ReleasePin('v1.18.2','145e5d2fc70983b89a4bdd8438e547fcd60244ed','a61005d37d01e6671f814fe8ca828222e8147df4');verify_release_pin(pg,pin);assert not subprocess.check_output(['git','status','--porcelain'],cwd=pg)
original='d10cfa8fb810b512333bcfa8b9d661493325478e';hashes={}
for n in ['maria/main.go','postgres/main.go','probe/probe.go','go.mod','go.sum']:
 data=(C/'benchmarks/forkcompare'/n).read_bytes();assert data==subprocess.check_output(['git','show',original+':benchmarks/forkcompare/'+n],cwd=C);hashes[n]=hashlib.sha256(data).hexdigest()
for phase in ['build','pilot','measure']:
 run([sys.executable,E/'run.py','--phase',phase],log=phase+'-console.txt')
 if phase=='build':
  p=E/'inputs.json';d=json.loads(p.read_text());d['original_harness_source_commit']=original;d['unchanged_harness_sha256']=hashes;d['orchestrator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();d['runner_sha256']=hashlib.sha256((E/'run.py').read_bytes()).hexdigest();d['replaces_verified']='Clean product checkout at6e29c1cd; clean pgmem typed v1.18.2 tag. go.mod replacement targets resolve to these exact directories.'
  env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0');graph=subprocess.check_output(['go','list','-m','-json','all'],cwd=T/'harness/benchmarks/forkcompare',env=env,text=True);d['module_graph']=graph.replace(str(T),'<temp>');p.write_text(json.dumps(d,indent=2)+'\n')
print('COMPLETE seconds',round(time.monotonic()-started,1),flush=True)
