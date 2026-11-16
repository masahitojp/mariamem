import os,sys,json,time,subprocess,resource,re,hashlib,statistics,random
from pathlib import Path
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence';d=e/'campaign';d.mkdir(exist_ok=True)
sys.path.insert(0,str(r/'scripts'));from experiment_disk import DiskGuard
guard=DiskGuard(w,8,6);guard.check();identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));inputs=json.loads((e/'inputs.json').read_text());assert identity==inputs['identity'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
assert hashlib.sha256((t/'maria.test').read_bytes()).hexdigest()==(e/'binary-sha256.txt').read_text()
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
for k in ['MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY','RESPONSE_PIPE','MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE','SKIP_READ_BODY','GODEBUG']:env.pop(k,None)
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';rows=[];deadline=time.monotonic()+900
(e/'measurement-method.json').write_text(json.dumps({'source_identity':identity,'blocks':10,'parallel':[8],'order':'ON OFF OFF ON / OFF ON ON OFF alternating','recursive_scan':'only before and after processes, never concurrent','timer':'external process wall and internal suite','limit_seconds':900},indent=2))
def trial(p,block,seq,arm):
 guard.check();assert time.monotonic()<deadline
 name=f'p{p}-b{block}-s{seq}-{arm}';trace=d/(name+'.json');log=d/(name+'.txt');load=os.getloadavg();utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());c0=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
 with log.open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(t/'maria.test'),'-test.run='+pattern,f'-test.parallel={p}','-test.timeout=150s'],cwd=t/'maria-suite',env=env|{'MODELCASE_TRACE':str(trace),'EXPERIMENT_BUFFER_LOAD':arm,'EXPERIMENT_VALIDATE_LOAD':'0'},stdout=f,stderr=f,timeout=min(180,max(1,deadline-time.monotonic())))
 wall=1000*(time.monotonic()-start);c1=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'name':name,'arm':arm,'p':p,'block':block,'seq':seq,'utc':utc,'code':q.returncode,'wall_ms':wall,'cpu_ms':1000*(c1.ru_utime+c1.ru_stime-c0.ru_utime-c0.ru_stime),'user_ms':1000*(c1.ru_utime-c0.ru_utime),'sys_ms':1000*(c1.ru_stime-c0.ru_stime),'voluntary_switches':c1.ru_nvcsw-c0.ru_nvcsw,'involuntary_switches':c1.ru_nivcsw-c0.ru_nivcsw,'load_before':load,'load_after':os.getloadavg()};rows.append(row);(e/'records.json').write_text(json.dumps(rows,indent=2));assert q.returncode==0,name
 j=json.loads(trace.read_text());sp=j['spans'];row['elapsed_ms']=j['elapsed_ms'];row['maxrss_bytes']=int(re.search(r'(\d+)\s+maximum resident set size',log.read_text())[1]);
 for phase,count in [('test',70),('fork',20),('sample',21),('writer_cleanup',20),('suite_run',1),('final_cleanup',1)]:assert sum(x['name']==phase for x in sp)==count,(name,phase)
 run=next(x for x in sp if x['name']=='suite_run');end=next(x for x in sp if x['name']=='final_cleanup');row['partition']={'setup_ms':run['start_ms'],'run_ms':run['end_ms']-run['start_ms'],'final_ms':end['end_ms']-end['start_ms']};row['partition']['other_ms']=row['elapsed_ms']-sum(row['partition'].values())
 row['phases']={}
 for phase in ['boot','import','snapshot','reader_fork','fork','sample','test','writer_cleanup']:
  xs=[x['end_ms']-x['start_ms'] for x in sp if x['name']==phase];row['phases'][phase]={'p50_ms':statistics.median(xs),'max_ms':max(xs),'sum_ms':sum(xs)}
 a=json.loads(j['meta']['runtime_metrics_start']);b=json.loads(j['meta']['runtime_metrics_end']);row['runtime_metrics']={k:b[k]-a[k]for k in a if not isinstance(a[k],dict)}
 k='/sched/latencies:seconds';assert a[k]['buckets']==b[k]['buckets'];counts=[y-x for x,y in zip(a[k]['counts'],b[k]['counts'])];row['sched_histogram']={'buckets':b[k]['buckets'],'counts':counts}
 row['last_writer']=max((x for x in sp if x['name']=='writer_cleanup'),key=lambda x:x['end_ms'])['lane']
 (e/'records.json').write_text(json.dumps(rows,indent=2));print(name,round(row['elapsed_ms'],3),flush=True);guard.check()
for seq,arm in enumerate(['ON','OFF']):trial(8,-1,seq,arm)
for block in range(10):
 order=['ON','OFF','OFF','ON'] if block%2==0 else ['OFF','ON','ON','OFF']
 for seq,arm in enumerate(order):trial(8,block,seq,arm)
assert len(rows)==42
print('ALL42SUITES_2940BODIES_PASS',flush=True)
