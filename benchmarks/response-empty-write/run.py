import json,os,sys,subprocess,shutil,time,resource,re,hashlib,random,platform
from pathlib import Path
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';r=w/'worktree';d=e/'campaign';d.mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',TRANSPORT_DIAG='0',SKIP_READ_BODY='0',MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE='0')
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
(e/'inputs.json').write_text(json.dumps({'identity':identity,'product_source_commit':'6558ee8fb2211313a8aa0ea6070ac5256767811a','platform':platform.platform(),'env':{k:env[k]for k in ['GOTOOLCHAIN','CGO_ENABLED','GOMAXPROCS','GOGC','MODELCASE_MATCHED','MARIA_AUDIT_OF','REVENUE_PREAGG','MARIA_ASYNC_CLOSE','TRANSPORT_DIAG','SKIP_READ_BODY']}},indent=2))
subprocess.run([sys.executable,str(r/'benchmarks/response-empty-write/make_overlay.py'),str(r),str(t)],check=True)
overlay=str(t/'overlay.json');(e/'overlay-hashes.json').write_text(json.dumps({str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [t/'base.go',r/'internal/generatedgo/code/base/base.go',r/'benchmarks/response-empty-write/experiment_empty_write_test.go.txt']},indent=2))
def command(args,cwd,log,extra={}):
 with (e/log).open('w')as f:subprocess.run(args,cwd=cwd,env=env|extra,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900)
for skip in [0,1]:command(['go','test','-overlay',overlay,'-p','1','-count=1','-timeout=90s','./internal/generatedgo/code/base'],r,f'base-tests-{skip}.txt',{'MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE':str(skip)})
command(['go','test','-overlay',overlay,'-p','1','-count=1','-timeout=90s','./internal/guest'],r,'guest-tests.txt')
print('BASE BOTH ARMS + GUEST TESTS PASS',flush=True)
src=r/'benchmarks/read-transport/harness';dst=t/'suite';shutil.copytree(src,dst);p=dst/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)));binary=t/'transport.test'
command(['go','test','-overlay',overlay,'-c','-p','1','-vet=off','-o',str(binary),'./store'],dst,'build.txt')
(e/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2))
def arm(mode,skip):return {'RESPONSE_PIPE':mode,'MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE':str(skip)}
for mode in ['os','go']:
 for skip in [0,1]:
  tag=f'{mode}-{skip}';cfg=arm(mode,skip)
  command([str(binary),'-test.run=^TestMatchedSemantics$','-test.timeout=120s'],dst,f'semantics-{tag}.txt',cfg)
  command([str(binary),'-test.run=^TestGetOrderCPUProbe$','-test.timeout=60s'],dst,f'diag-{tag}.txt',cfg|{'TRANSPORT_DIAG':'1'})
  profile=e/f'{tag}.pprof'
  command([str(binary),'-test.run=^TestGetOrderCPUProbe$','-test.timeout=60s'],dst,f'profile-{tag}.txt',cfg|{'READ_CPU_PROFILE':str(profile)})
  for kind,args in [('flat',['-top']),('cum',['-top','-cum'])]:command(['go','tool','pprof',*args,str(binary),str(profile)],dst,f'profile-{tag}-{kind}.txt')
  print('SEMANTICS COUNTERS PROFILE',tag,'PASS',flush=True)
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';rows=[]
def trial(workload,phase,comp,rep,label,mode,skip):
 name=f'{workload}-{mode}-{phase}-{comp}-{rep}-{label}';trace=d/(name+'.json');a=time.monotonic();c0=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (d/(name+'.txt')).open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(binary),'-test.run='+(pattern if workload=='suite'else'^TestGetOrderCPUProbe$'),'-test.parallel=8','-test.timeout=150s'],cwd=dst,env=env|arm(mode,skip)|{'MODELCASE_TRACE':str(trace)},stdout=f,stderr=f,timeout=180)
 c1=resource.getrusage(resource.RUSAGE_CHILDREN);assert q.returncode==0,name;j=json.loads(trace.read_text());sp=j['spans']
 if workload=='suite':assert sum(x['name']=='test'for x in sp)==70 and sum(x['name']=='fork'for x in sp)==20
 row={'workload':workload,'phase':phase,'comparison':comp,'rep':rep,'label':label,'mode':mode,'skip':skip,'name':name,'suite_ms':j['elapsed_ms'],'process_ms':1000*(time.monotonic()-a),'cpu_ms':1000*(c1.ru_utime+c1.ru_stime-c0.ru_utime-c0.ru_stime)}
 if workload=='query':row['query_ms']=float(re.search(r'GETORDER4000_MS ([0-9.]+)',(d/(name+'.txt')).read_text())[1])
 rows.append(row);(e/'runs.json').write_text(json.dumps(rows,indent=2));print(name,round(row.get('query_ms',row['suite_ms']),3),flush=True)
for workload in ['query','suite']:
 for mode in ['os','go']:
  for skip in [0,1]:trial(workload,'warmup','warmup',-1,str(skip),mode,skip)
 rnd=random.Random(119)
 for rep in range(5):
  jobs=[(m,c)for m in ['os','go']for c in ['aa','ab']];rnd.shuffle(jobs)
  for mode,comp in jobs:
   for i in ([0,1]if rep%2==0 else[1,0]):trial(workload,'measure',comp,rep,['A','B'][i],mode,int(comp=='ab'and i==1))
print('ALL88 TIMING PROCESSES PASS',flush=True)
