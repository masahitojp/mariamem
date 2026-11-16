import json,os,sys,subprocess,shutil,time,resource,re,statistics,hashlib,platform
from pathlib import Path
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';r=w/'worktree'
e.mkdir(exist_ok=True);d=e/'campaign';d.mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',TMPDIR=str(t/'tmp'),GOTMPDIR=str(t/'go-tmp'),GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1')
for k in ['MARIA_ASYNC_CLOSE','RESPONSE_PIPE','MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE','SKIP_READ_BODY','GODEBUG','MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY']:env.pop(k,None)
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
pgid=json.loads(subprocess.check_output([sys.executable,str(r/'scripts/git_identity.py'),'--root',str(t/'pgmem'),'inspect','HEAD']));assert pgid['source_commit']=='3433a40bd4167daea2d8e364666bd5fcf18ef654';assert not subprocess.check_output(['git','status','--porcelain'],cwd=t/'pgmem')
inputs={'harness_identity':identity,'maria_source_commit':'454121d62a9aba26a0516f022e0c0ed77b30b33e','pg_identity':pgid,'platform':platform.platform(),'env':{k:env[k] for k in ['GOTOOLCHAIN','CGO_ENABLED','GOMAXPROCS','GOGC','MODELCASE_MATCHED','MARIA_AUDIT_OF','REVENUE_PREAGG']},'binary':{}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2))
for arm in ['maria','pg']:
 dst=t/(arm+'-suite');dst.mkdir(exist_ok=True)
 prefix='benchmarks/comparison-variance/harness/'+arm+'-suite/'
 for name in subprocess.check_output(['git','ls-tree','-r','--name-only','1977fff4',prefix],cwd=r,text=True).splitlines():
  target=dst/name[len(prefix):];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(subprocess.check_output(['git','show','1977fff4:'+name],cwd=r))
 p=dst/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)).replace('<PGMEM_SOURCE>',str(t/'pgmem')))
 with (e/(arm+'-build.txt')).open('w') as f:subprocess.run(['go','test','-c','-p','1','-vet=off','-o',str(t/(arm+'.test')),'./store'],cwd=dst,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 inputs['binary'][arm]={'sha256':hashlib.sha256((t/(arm+'.test')).read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(t/(arm+'.test'))],env=env,text=True)}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2))
for arm in ['maria','pg']:
 with (e/(arm+'-semantics.txt')).open('w')as f:subprocess.run([str(t/(arm+'.test')),'-test.run=^TestMatchedSemantics$','-test.timeout=150s'],cwd=t/(arm+'-suite'),env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 print(arm,'semantics PASS',flush=True)
print('BUILD_AND_SEMANTICS_COMPLETE',flush=True)
