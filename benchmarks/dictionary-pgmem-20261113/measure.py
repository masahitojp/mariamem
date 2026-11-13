from pathlib import Path
import ctypes,json,os,subprocess,time,sys,hashlib,platform
w=Path(__file__).resolve().parents[1];t=w/'temp';s=t/'harness';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from experiment_disk import DiskGuard,stop_group
class Usage(ctypes.Structure):
 _fields_=[('uuid',ctypes.c_uint8*16)]+[(n,ctypes.c_uint64) for n in ('user','system','idle','interrupt','pageins','wired','rss','footprint','start','exit')]
lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True);lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];lib.proc_pid_rusage.restype=ctypes.c_int
def rss(pid):
 u=Usage();assert lib.proc_pid_rusage(pid,0,ctypes.byref(u))==0;return u.rss
save=lambda name,v:(e/name).write_text(json.dumps(v,indent=2)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((e/'inputs.json').read_text());assert json.loads((e/'build-complete.json').read_text())['result']=='PASS'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['harness_source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True)
for label,v in inputs['binaries'].items():assert sha(t/'bin'/label)==v['sha256']
for label,v in inputs['products'].items():assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=t/label,text=True).strip()==v['source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=t/label,text=True)
a=rss(os.getpid());b=int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]))*1024;assert a>0 and abs(a-b)<8*1024**2
save('sampler.json',{'libproc_rss':a,'ps_rss':b,'sample_interval_ms':20,'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'logical_cpus':int(subprocess.check_output(['sysctl','-n','hw.ncpu'],text=True))})
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))};env.update(GOMAXPROCS='8',GOGC='100')
guard=DiskGuard(w,12,12);records=[];variants={'baseline-pipe':('baseline','pipe'),'candidate-pipe':('candidate','pipe'),'pgmem-pipe':('pgmem','pipe')}
def run(variant,p,rep,count=48,negative=False,warmup=False):
 binary,route=variants[variant];label=f'{variant}-p{p}-r{rep}'+('-negative' if negative else '-warmup' if warmup else '')
 out=e/(label+'.json');sync=t/'sync'/label;scratch=t/'scratch'/label;sync.mkdir(parents=True);scratch.mkdir(parents=True);cmd=[str(t/'bin'/binary),'-out',str(out),'-route',route,'-parallel',str(p),'-count',str(count),'-sync-dir',str(sync)]+(['-corrupt-seed'] if negative else [])
 guard.check();process=None;samples=[];baseline=None;start=time.perf_counter_ns()
 with (e/(label+'.log')).open('w') as log:
  try:
   process=subprocess.Popen(cmd,cwd=s/'benchmarks/forkcompare',env=dict(env,TMPDIR=str(scratch)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True);deadline=time.monotonic()+120
   while not (sync/'ready').exists():
    assert process.poll() is None and time.monotonic()<deadline,'ready/early-exit failure: '+label
    time.sleep(.02)
   baseline=rss(process.pid);begin=time.monotonic();(sync/'go').write_text('go')
   while not (sync/'done').exists():
    assert time.monotonic()<deadline and process.poll() is None,'batch failure: '+label
    samples.append({'offset_ms':(time.monotonic()-begin)*1000,'rss_bytes':rss(process.pid)});time.sleep(.02)
   process.wait(timeout=30);code=process.returncode;wall=(time.perf_counter_ns()-start)/1e6
  finally:
   if process is not None:stop_group(process)
 guard.check();d=json.loads(out.read_text());assert d['cleanup_complete'] and not any(scratch.iterdir());assert d['root_closed_before_forks'] and d['gomaxprocs']==8 and d['parallel']==p and d['route']==route
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
 else:
  assert code==0 and d['success'] and len(d['samples'])==count and {v['index'] for v in d['samples']}==set(range(count));assert all(v['oracle'] and v['cleanup_complete'] for v in d['samples'])
 events=sorted([(v['offset_ms'],1) for v in d['samples']]+[(v['offset_ms']+v['total_ms'],-1) for v in d['samples']]);active=peak=0
 for _,delta in events:active+=delta;peak=max(peak,active)
 assert active==0 and peak<=p
 if not negative:assert peak==p
 mem={'baseline_rss_bytes':baseline,'sampled_peak_rss_bytes':max((v['rss_bytes'] for v in samples), default=None),'samples':samples,'interval_ms':20,'peak_active_children':peak};save(label+'-memory.json',mem)
 records.append({'variant':variant,'parallel':p,'repetition':rep,'count':count,'negative':negative,'warmup':warmup,'report':out.name,'memory':label+'-memory.json','process_wall_ms':wall,'returncode':code,'binary_sha256':inputs['binaries'][binary]['sha256']});save('records.json',records);print(label,'PASS',round(d['batch_ms'],1),'ms',flush=True)
save("host-preflight.json", {"processes":subprocess.check_output(["ps","-axo","pid,ppid,%cpu,comm"],text=True).replace(str(w),"<WORKSPACE>"),"power":subprocess.check_output(["pmset","-g","batt"],text=True),"vm_stat":subprocess.check_output(["vm_stat"],text=True)})
for v in variants:run(v,8,-2,8);run(v,1,-2,1,negative=True)
save('pilots.json',{'result':'PASS','positive':3,'negative':3,'phase_and_cleanup_oracles':'PASS'})
for p in [4,8]:
 for v in variants:run(v,p,-1,warmup=True)
labels=list(variants)
for rep in range(5):
 for p in ([4,8] if rep%2==0 else [8,4]):
  shift=(rep+(2 if p==8 else 0))%3;order=labels[shift:]+labels[:shift]
  for v in order:run(v,p,rep)
save('measurement-complete.json',{'result':'PASS','measured_processes':30,'warmup_processes':6,'children_per_process':48,'pilots':6,'no_sample_removed':True,'controller_sha256':sha(Path(__file__)),'harness_source_commit':inputs['harness_source_commit'],'peak_workspace_bytes':guard.peak,'min_free_bytes':guard.minimum_free})
