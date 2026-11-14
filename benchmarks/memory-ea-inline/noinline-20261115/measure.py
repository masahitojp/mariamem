from pathlib import Path
import json,subprocess,os,time,resource,re,statistics,shutil
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';D=E/'campaign';D.mkdir(exist_ok=True);rows=[];started=time.monotonic()
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1')
for k in ['MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY']:env.pop(k,None)
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$'
for parallel in [1,4,8]:
 for iteration in ['warm',*map(str,range(5))]:
  labels=['baseline','direct','noinline'];i=0 if iteration=='warm' else int(iteration)%3;labels=labels[i:]+labels[:i]
  for label in labels:
   assert time.monotonic()-started<900 and shutil.disk_usage(T).free>=6*1024**3
   name=f'p{parallel}-{iteration}-{label}';trace=D/(name+'.json');a=time.monotonic();r0=resource.getrusage(resource.RUSAGE_CHILDREN)
   with (D/(name+'.txt')).open('w')as f:r=subprocess.run(['/usr/bin/time','-l',str(T/(label+'.test')),'-test.run='+pattern,f'-test.parallel={parallel}','-test.timeout=150s'],cwd=T/'maria-suite',env=dict(env,MODELCASE_TRACE=str(trace)),stdout=f,stderr=f,timeout=180)
   r1=resource.getrusage(resource.RUSAGE_CHILDREN);row=dict(name=name,p=parallel,iteration=iteration,label=label,code=r.returncode,wall_ms=(time.monotonic()-a)*1000,cpu_ms=1000*((r1.ru_utime+r1.ru_stime)-(r0.ru_utime+r0.ru_stime)));rows.append(row);(E/'records.json').write_text(json.dumps(rows,indent=2));assert r.returncode==0,name
   text=(D/(name+'.txt')).read_text();m=re.search(r'(\d+)\s+maximum resident set size',text);assert m;row['maxrss_bytes']=int(m[1]);j=json.loads(trace.read_text());spans=j['spans'];assert sum(z['name']=='test'for z in spans)==70;assert sum(z['name']=='fork'for z in spans)==20
   assert sum(z['name']=='sample' for z in spans)==21
   row['elapsed_ms']=j['elapsed_ms'];row['phases']={}
   for phase in ['boot','import','snapshot','reader_fork','fork','sample','test']:
    xs=[z['end_ms']-z['start_ms']for z in spans if z['name']==phase];row['phases'][phase]={'count':len(xs),'sum_ms':sum(xs),'p50_ms':statistics.median(xs)if xs else 0}
   (E/'records.json').write_text(json.dumps(rows,indent=2));print(name,round(row['elapsed_ms'],3),flush=True)
assert len(rows)==54
print('ALL 54 SUITES PASS',flush=True)
