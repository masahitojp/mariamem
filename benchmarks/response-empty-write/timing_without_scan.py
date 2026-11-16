import json,os,sys,subprocess,shutil,time,resource,re,hashlib,random,platform
from pathlib import Path
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';r=w/'worktree';d=e/'campaign';d.mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',TRANSPORT_DIAG='0',SKIP_READ_BODY='0',MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE='0')
sys.path.insert(0,str(r/'scripts'))
from experiment_disk import DiskGuard
guard=DiskGuard(w,8,6)
guard.check()
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r))
assert identity['source_commit']=='aa2cfda3ca9d265a996bd5a2398b659ccab769fe'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
binary=t/'transport.test';dst=t/'suite'
assert hashlib.sha256(binary.read_bytes()).hexdigest()==json.loads((e/'binary.json').read_text())['sha256']
deadline=time.monotonic()+900
(e/'timing-method.json').write_text(json.dumps({'correction':'no concurrent recursive workspace scan; capacity checks before/after each timed process','old_guard':'run_guarded default0.5s recursive check; retained scanning-guard-cohort','source_identity':identity,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'fixed_timing_processes':88,'wall_budget_seconds':900},indent=2))
def arm(mode,skip):return {'RESPONSE_PIPE':mode,'MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE':str(skip)}
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';rows=[]
def trial(workload,phase,comp,rep,label,mode,skip):
 name=f'{workload}-{mode}-{phase}-{comp}-{rep}-{label}';trace=d/(name+'.json');guard.check();assert time.monotonic()<deadline;a=time.monotonic();c0=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (d/(name+'.txt')).open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(binary),'-test.run='+(pattern if workload=='suite'else'^TestGetOrderCPUProbe$'),'-test.parallel=8','-test.timeout=150s'],cwd=dst,env=env|arm(mode,skip)|{'MODELCASE_TRACE':str(trace)},stdout=f,stderr=f,timeout=min(180,max(1,deadline-time.monotonic())))
 c1=resource.getrusage(resource.RUSAGE_CHILDREN);assert q.returncode==0,name;j=json.loads(trace.read_text());sp=j['spans']
 if workload=='suite':assert sum(x['name']=='test'for x in sp)==70 and sum(x['name']=='fork'for x in sp)==20
 row={'workload':workload,'phase':phase,'comparison':comp,'rep':rep,'label':label,'mode':mode,'skip':skip,'name':name,'suite_ms':j['elapsed_ms'],'process_ms':1000*(time.monotonic()-a),'cpu_ms':1000*(c1.ru_utime+c1.ru_stime-c0.ru_utime-c0.ru_stime)}
 if workload=='query':row['query_ms']=float(re.search(r'GETORDER4000_MS ([0-9.]+)',(d/(name+'.txt')).read_text())[1])
 rows.append(row);(e/'runs.json').write_text(json.dumps(rows,indent=2));print(name,round(row.get('query_ms',row['suite_ms']),3),flush=True);guard.check()
for workload in ['query','suite']:
 for mode in ['os','go']:
  for skip in [0,1]:trial(workload,'warmup','warmup',-1,str(skip),mode,skip)
 rnd=random.Random(119)
 for rep in range(5):
  jobs=[(m,c)for m in ['os','go']for c in ['aa','ab']];rnd.shuffle(jobs)
  for mode,comp in jobs:
   for i in ([0,1]if rep%2==0 else[1,0]):trial(workload,'measure',comp,rep,['A','B'][i],mode,int(comp=='ab'and i==1))
print('ALL88 TIMING PROCESSES PASS',flush=True)
