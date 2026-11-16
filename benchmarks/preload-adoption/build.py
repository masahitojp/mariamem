import os,subprocess,json,shutil,hashlib,sys
from pathlib import Path
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence'
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),GOTMPDIR=str(t/'tmp'),TMPDIR=str(t/'tmp'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1')
(t/'tmp').mkdir(exist_ok=True);shutil.copytree(r/'benchmarks/comparison-variance/harness/maria-suite',t/'maria-suite',dirs_exist_ok=True)
p=t/'maria-suite/go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)))
(e/'inputs.json').write_text(json.dumps({'identity':identity,'env':{k:env[k] for k in ['GOTOOLCHAIN','CGO_ENABLED','GOMAXPROCS','GOGC','MODELCASE_MATCHED','MARIA_AUDIT_OF','REVENUE_PREAGG']}},indent=2))
with (e/'build.txt').open('w')as f:subprocess.run(['go','test','-c','-p','1','-vet=off','-o',str(t/'maria.test'),'./store'],cwd=t/'maria-suite',env=env,stdout=f,stderr=f,check=True)
(e/'binary-sha256.txt').write_text(hashlib.sha256((t/'maria.test').read_bytes()).hexdigest())
for mode in ['ON','OFF']:
 with (e/('validate-'+mode+'.txt')).open('w')as f:subprocess.run([str(t/'maria.test'),'-test.run=^TestMatchedSemantics$','-test.timeout=150s'],cwd=t/'maria-suite',env=env|{'EXPERIMENT_BUFFER_LOAD':mode,'EXPERIMENT_VALIDATE_LOAD':'1'},stdout=f,stderr=f,check=True)
 print(mode,'VALIDATED',flush=True)

with (e/'large-build.txt').open('w')as f:subprocess.run(['go','build','-p','1','-o',str(t/'large'),'./preload-adoption'],cwd=r/'benchmarks',env=env,stdout=f,stderr=f,check=True)
(e/'large-sha256.txt').write_text(hashlib.sha256((t/'large').read_bytes()).hexdigest())
for arm in ['ON','OFF']:
 with (e/('acceptance-'+arm+'.txt')).open('w')as f:subprocess.run([str(t/'large'),'-rows=4096','-p=8','-acceptance','-out='+str(e/('acceptance-'+arm+'.json'))],cwd=r,env=env|{'EXPERIMENT_BUFFER_LOAD':arm},stdout=f,stderr=f,check=True)
 print(arm,'ISOLATION_RESNAPSHOT_CLEANUP_PASS',flush=True)
