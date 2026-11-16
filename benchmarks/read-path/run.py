import json,os,sys,subprocess,shutil,time,resource,re,statistics,hashlib,random
from pathlib import Path
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';r=w/'worktree';d=e/'campaign';d.mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
(e/'inputs.json').write_text(json.dumps({'identity':identity,'product_source_commit':'6558ee8fb2211313a8aa0ea6070ac5256767811a','env':{k:env[k]for k in ['GOTOOLCHAIN','CGO_ENABLED','GOMAXPROCS','GOGC']}},indent=2))
src=r/'benchmarks/read-path/harness';dst=t/'suite';shutil.copytree(src,dst);p=dst/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)))
binary=t/'read.test'
with (e/'build.txt').open('w')as f:subprocess.run(['go','test','-c','-p','1','-vet=off','-o',str(binary),'./store'],cwd=dst,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
(e/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2))
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';rows=[]
def trial(phase,comp,rep,label,skip):
 name=f'{phase}-{comp}-{rep}-{label}';trace=d/(name+'.json');a=time.monotonic();c0=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (d/(name+'.txt')).open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(binary),'-test.run='+pattern,'-test.parallel=8','-test.timeout=150s'],cwd=dst,env=dict(env,SKIP_READ_BODY=str(skip),MODELCASE_TRACE=str(trace)),stdout=f,stderr=f,timeout=180)
 c1=resource.getrusage(resource.RUSAGE_CHILDREN);assert q.returncode==0,name;j=json.loads(trace.read_text());sp=j['spans'];assert sum(x['name']=='test'for x in sp)==70 and sum(x['name']=='fork'for x in sp)==20
 row={'phase':phase,'comparison':comp,'rep':rep,'label':label,'skip':skip,'name':name,'suite_ms':j['elapsed_ms'],'process_ms':1000*(time.monotonic()-a),'cpu_ms':1000*(c1.ru_utime+c1.ru_stime-c0.ru_utime-c0.ru_stime)}
 row['read_end_ms']=max(x['end_ms']for x in sp if x['name']=='test'and x['kind']=='read');row['write_end_ms']=max(x['end_ms']for x in sp if x['name']=='test'and x['kind']=='write');rows.append(row);(e/'runs.json').write_text(json.dumps(rows,indent=2));print(name,round(row['suite_ms'],3),flush=True)
for skip in [0,1]:trial('warmup','warmup',-1,str(skip),skip)
rnd=random.Random(119)
for rep in range(5):
 jobs=['aa','ab'];rnd.shuffle(jobs)
 for comp in jobs:
  for i in ([0,1]if rep%2==0 else[1,0]):trial('measure',comp,rep,['A','B'][i],int(comp=='ab'and i==1))
for i in range(3):
 profile=t/f'getorder-{i}.pprof'
 with (e/f'getorder-{i}.txt').open('w')as f:subprocess.run([str(binary),'-test.run=^TestGetOrderCPUProbe$','-test.timeout=60s'],cwd=dst,env=dict(env,READ_CPU_PROFILE=str(profile)),stdout=f,stderr=f,check=True)
 for kind,args in [('flat',['-top']),('cum',['-top','-cum']),('raw',['-raw'])]:
  with (e/f'profile-{i}-{kind}.txt').open('w')as f:subprocess.run(['go','tool','pprof',*args,str(binary),str(profile)],cwd=dst,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 print('profile',i,'PASS',flush=True)
print('ALL22SUITES+3PROBES PASS',flush=True)
