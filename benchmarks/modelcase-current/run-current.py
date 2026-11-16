import json,os,sys,subprocess,shutil,time,resource,re,statistics,hashlib,platform
from pathlib import Path
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence/final';r=w/'worktree'
e.mkdir(exist_ok=True);d=e/'campaign';d.mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',TMPDIR=str(t/'tmp'),GOTMPDIR=str(t/'go-tmp'),GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1')
for k in ['MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY']:env.pop(k,None)
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
pgid=json.loads(subprocess.check_output([sys.executable,str(r/'scripts/git_identity.py'),'--root',str(t/'pgmem'),'inspect','HEAD']));assert pgid['source_commit']=='3433a40bd4167daea2d8e364666bd5fcf18ef654';assert not subprocess.check_output(['git','status','--porcelain'],cwd=t/'pgmem')
inputs={'harness_identity':identity,'maria_source_commit':'6558ee8fb2211313a8aa0ea6070ac5256767811a','pg_identity':pgid,'platform':platform.platform(),'env':{k:env[k] for k in ['GOTOOLCHAIN','CGO_ENABLED','GOMAXPROCS','GOGC','MODELCASE_MATCHED','MARIA_AUDIT_OF','REVENUE_PREAGG']},'binary':{}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2))
for arm in ['maria','pg']:
 src=r/'benchmarks/modelcase-current/harness'/(arm+'-suite');dst=t/(arm+'-suite');shutil.copytree(src,dst,dirs_exist_ok=True)
 p=dst/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)).replace('<PGMEM_SOURCE>',str(t/'pgmem')))
 with (e/(arm+'-build.txt')).open('w') as f:subprocess.run(['go','test','-c','-p','1','-vet=off','-o',str(t/(arm+'.test')),'./store'],cwd=dst,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 inputs['binary'][arm]={'sha256':hashlib.sha256((t/(arm+'.test')).read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(t/(arm+'.test'))],env=env,text=True)}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2))
for arm in ['maria','pg']:
 with (e/(arm+'-semantics.txt')).open('w')as f:subprocess.run([str(t/(arm+'.test')),'-test.run=^TestMatchedSemantics$','-test.timeout=150s'],cwd=t/(arm+'-suite'),env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 print(arm,'semantics PASS',flush=True)
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';rows=[]
for p in [1,4,8]:
 for iteration in ['warm',*map(str,range(5))]:
  order=['maria-sync','maria-async','pg'];rot=0 if iteration=='warm' else int(iteration)%3;order=order[rot:]+order[:rot]
  for label in order:
   arm='pg'if label=='pg'else'maria';name=f'p{p}-{iteration}-{label}';trace=d/(name+'.json');utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());a=time.monotonic();r0=resource.getrusage(resource.RUSAGE_CHILDREN)
   with (d/(name+'.txt')).open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(t/(arm+'.test')),'-test.run='+pattern,f'-test.parallel={p}','-test.timeout=150s'],cwd=t/(arm+'-suite'),env=dict(env,MODELCASE_TRACE=str(trace),MARIA_ASYNC_CLOSE='1'if label=='maria-async'else'0'),stdout=f,stderr=f,timeout=180)
   r1=resource.getrusage(resource.RUSAGE_CHILDREN);row=dict(name=name,p=p,iteration=iteration,label=label,code=q.returncode,utc=utc,wall_ms=(time.monotonic()-a)*1000,cpu_ms=1000*((r1.ru_utime+r1.ru_stime)-(r0.ru_utime+r0.ru_stime)));rows.append(row);(e/'records.json').write_text(json.dumps(rows,indent=2));assert q.returncode==0,name
   log=(d/(name+'.txt')).read_text();row['maxrss_bytes']=int(re.search(r'(\d+)\s+maximum resident set size',log)[1]);j=json.loads(trace.read_text());spans=j['spans']
   for phase,count in [('test',70),('fork',20),('sample',21)]:assert sum(x['name']==phase for x in spans)==count
   row['elapsed_ms']=j['elapsed_ms'];row['phases']={}
   for phase in ['boot','import','snapshot','reader_fork','fork','sample','test','cleanup_drain']:
    xs=[x['end_ms']-x['start_ms']for x in spans if x['name']==phase];row['phases'][phase]={'count':len(xs),'sum_ms':sum(xs),'p50_ms':statistics.median(xs)if xs else 0}
   (e/'records.json').write_text(json.dumps(rows,indent=2));print(name,round(row['elapsed_ms'],3),flush=True)
assert len(rows)==54;print('ALL54SUITES PASS',flush=True)
