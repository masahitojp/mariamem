from pathlib import Path
import hashlib,json,os,platform,signal,subprocess,sys,time
W=Path(__file__).resolve().parents[1];T=W/'temp';S=T/'source';E=W/'evidence';R=W.parents[2]
sys.path.insert(0,str(S/'scripts'))
from experiment_disk import DiskGuard,stop_group
from experiment_workspace import exclusive,load,save
def write(name,v):(E/name).write_text(json.dumps(v,indent=2)+'\n')
inputs=json.loads((E/'inputs.json').read_text());assert json.loads((E/'build-complete.json').read_text())['result']=='PASS'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==inputs['harness_source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=S,text=True)
for label,v in inputs['binaries'].items():assert hashlib.sha256((T/'bin'/label).read_bytes()).hexdigest()==v['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','FORKCOST_','FORKSTAGES_','GODEBUG','GOGC','GOMEMLIMIT','GOFLAGS'))};env.update(GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local')
guard=DiskGuard(W,12,12);records=[]
def one(label,p,mode,rep,count=48,negative=False):
 name=f'{label}-p{p}-{mode}-r{rep}'+('-negative' if negative else '')
 work=T/'scratch'/name;work.mkdir();tmp=work/'tmp';tmp.mkdir();tr=work/'traces';tr.mkdir();out=E/(name+'.json');v=dict(env,TMPDIR=str(tmp))
 if mode=='traced':
  v['FORKCOST_TRACE']=str(E/(name+'-traces.json'))
  if label=='maria':v['MARIAMEM_TIMING_DIR']=str(tr)
 if mode=='profile':v['FORKSTAGES_CPU']=str(E/(name+'.pprof'))
 cmd=[str(T/'bin'/label),'-route','pipe','-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 guard.check();process=None
 with (E/(name+'.txt')).open('w') as log:
  try:
   process=subprocess.Popen(cmd,cwd=S/'benchmarks/forkcompare',env=v,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   code=process.wait(timeout=120)
  finally:
   if process is not None:stop_group(process)
 guard.check();d=json.loads(out.read_text());assert d['cleanup_complete'] and d['root_closed_before_forks'] and not any(tmp.iterdir());assert d['parallel']==p and d['route']=='pipe' and d['gomaxprocs']==8
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
 else:assert code==0 and d['success'] and len(d['samples'])==count and {s['index'] for s in d['samples']}==set(range(count)) and all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
 if mode=='traced':
  traces=json.loads((E/(name+'-traces.json')).read_text());assert set(traces['children'])=={str(s['index']) for s in d['samples']}
  for c in traces['children'].values():
   if label=='maria':
    assert set(c['traces'])=={'fork','api_startup','startup','api_close','host_close','runtime_threads_close','runtime_memory_close','runtime_files_close'},set(c['traces'])
    assert 'guest' in c['traces']['startup']
   else:
    ops={x['operation'] for x in c['events']};assert {'pg_fork','pg_boot','pg_cluster','pg_close','pg_cluster_release'}<=ops
 if mode=='profile':
  for kind,args in [('top',['-top','-nodecount=40']),('memclr',['-tree','-nodecount=50','-focus=memclr']),('mmap',['-tree','-nodecount=50','-focus=Mmap|Munmap|Mprotect|mmap|munmap|mprotect'])]:
   with (E/(name+'-'+kind+'.txt')).open('w') as log:subprocess.run(['go','tool','pprof',*args,str(T/'bin'/label),str(E/(name+'.pprof'))],env=v,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=45)
 records.append({'variant':label,'parallel':p,'mode':mode,'repetition':rep,'negative':negative,'count':count,'returncode':code,'report':out.name,'traces':name+'-traces.json' if mode=='traced' else None,'binary_sha256':inputs['binaries'][label]['sha256']});write('records.json',records)
 print(name,'PASS',round(d['batch_ms'],2),flush=True)
def timeout(signum,frame):raise TimeoutError('measurement phase timeout/interruption')
signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGTERM,timeout)
with exclusive(W):
 record=load(W,R);assert record['state']=='completed';record['state']='running';save(W,record);signal.alarm(900)
 try:
  write('host.json',{'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'power':subprocess.check_output(['pmset','-g','batt'],text=True),'processes':subprocess.check_output(['ps','-axo','pid,ppid,%cpu,comm'],text=True)})
  for label in ['maria','pgmem']:one(label,8,'traced',-2,8);one(label,1,'traced',-2,1,True)
  for p in [1,4,8]:
   for label in ['maria','pgmem']:
    for mode in ['plain','traced']:one(label,p,mode,-1)
  for rep in range(3):
   for p in ([1,4,8] if rep%2==0 else [8,4,1]):
    for label in (['maria','pgmem'] if rep%2==0 else ['pgmem','maria']):
     for mode in (['plain','traced'] if rep%2==0 else ['traced','plain']):one(label,p,mode,rep)
  for p in [1,8]:
   for label in ['maria','pgmem']:one(label,p,'profile',0,96)
  write('measurement-complete.json',{'result':'PASS','ordinary_processes':36,'warmup_processes':12,'pilots':4,'profiles':4,'no_samples_removed':True,'peak_workspace_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free,'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
 except BaseException:record['state']='failed';raise
 else:record['state']='completed'
 finally:signal.alarm(0);save(W,record)
