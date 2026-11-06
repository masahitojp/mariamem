from pathlib import Path
import ctypes,json,os,subprocess,time,sys,hashlib,platform
w=Path(__file__).resolve().parents[1];t=w/'temp';s=w/'worktree';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from experiment_disk import DiskGuard,stop_group
class Usage(ctypes.Structure):
 _fields_=[('uuid',ctypes.c_uint8*16)]+[(n,ctypes.c_uint64) for n in ('user','system','idle','interrupt','pageins','wired','rss','footprint','start','exit')]
lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True);lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];lib.proc_pid_rusage.restype=ctypes.c_int
def rss(pid):
 u=Usage();assert lib.proc_pid_rusage(pid,0,ctypes.byref(u))==0;return u.rss

save=lambda name,v:(e/name).write_text(json.dumps(v,indent=2)+'\n')
inputs=json.loads((e/'inputs.json').read_text());plan=json.loads((e/'plan.json').read_text())
assert not (e/'records.json').exists(),'Do not repeat a started protocol'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['controller_source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=s).strip()
for arm,a in inputs['arms'].items():
 assert hashlib.sha256((t/(arm+'-probe')).read_bytes()).hexdigest()==a['binary_sha256']
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=t/arm,text=True).strip()==a['source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=t/arm).strip()
a=rss(os.getpid());b=int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]))*1024;assert a>0 and abs(a-b)<8*1024**2
save('sampler.json',{'libproc_rss':a,'ps_rss':b,'sample_interval_ms':20,'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'logical_cpus':int(subprocess.check_output(['sysctl','-n','hw.ncpu'],text=True))})
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS','FORKSTAGES_','DEFAULT_SETTINGS_','ISSUE116_','UPDATE_WAIT_','UPDATE_NOTIFY_'))};env.update(GOMAXPROCS='8',GOGC='100');guard=DiskGuard(w,12,8);records=[]
def run(arm,p,rep,count=48,negative=False,warmup=False,preflight=False):
 variant="both-off"
 label=f'{arm}-p{p}-r{rep}'+('-negative' if negative else '-preflight' if preflight else '-warmup' if warmup else '')
 out=e/(label+'.json');sync=t/'sync'/label;scratch=t/'scratch'/label;sync.mkdir(parents=True);scratch.mkdir(parents=True);cmd=[str(t/(arm+'-probe')),'-out',str(out),'-route','pipe','-parallel',str(p),'-count',str(count),'-sync-dir',str(sync)]+(['-corrupt-seed'] if negative else [])
 v=dict(env,TMPDIR=str(scratch),DEFAULT_SETTINGS_VARIANT=variant)
 traces=t/'trace'/label;stacks=t/'stack'/label;traces.mkdir(parents=True);stacks.mkdir(parents=True)
 if arm=='owner':v.update(UPDATE_NOTIFY_DIR=str(traces),UPDATE_WAIT_DIR=str(stacks))
 if preflight:v['DEFAULT_SETTINGS_PREFLIGHT']='1'
 guard.check();process=None;samples=[];baseline=None;start=time.perf_counter_ns()
 with (e/(label+'.log')).open('w') as log:
  try:
   process=subprocess.Popen(cmd,cwd=t/arm/'benchmarks/forkcompare',env=v,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);deadline=time.monotonic()+120
   while not (sync/'ready').exists():
    assert process.poll() is None and time.monotonic()<deadline,'ready/early-exit failure: '+label
    size=rss(process.pid);assert size<3*1024**3,'RSS limit before batch';time.sleep(.02)
   baseline=rss(process.pid);begin=time.monotonic();(sync/'go').write_text('go')
   while not (sync/'done').exists():
    assert time.monotonic()<deadline and process.poll() is None,'batch failure: '+label
    size=rss(process.pid);assert size<3*1024**3,'RSS limit during batch';samples.append({'offset_ms':(time.monotonic()-begin)*1000,'rss_bytes':size});time.sleep(.02)
   process.wait(timeout=30);code=process.returncode;wall=(time.perf_counter_ns()-start)/1e6
  finally:
   if process is not None:stop_group(process)
 guard.check();d=json.loads(out.read_text());assert d['cleanup_complete'] and not any(scratch.iterdir());assert d['root_closed_before_forks'] and d['gomaxprocs']==8 and d['parallel']==p and d['route']=='pipe'
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
 else:
  assert code==0 and d['success'] and len(d['samples'])==count and {v['index'] for v in d['samples']}==set(range(count));assert all(v['oracle'] and v['cleanup_complete'] and all(v[k]>=0 for k in ['count_ms','update_ms','check_ms','retire_ms','wait_ms','close_ms']) and v['count_ms']+v['update_ms']+v['check_ms']<=v['sql_ms']+.01 for v in d['samples'])
 assert all(v['retire_ms']+v['wait_ms']+v['close_ms']<=v['cleanup_ms']+.02 for v in d['samples'])
 if preflight:
  configs=[d['config']]+[v['config'] for v in d['samples']]
  for config in configs:
   expected={'innodb_buffer_pool_size':'16777216','innodb_buffer_pool_size_max':'16777216','innodb_log_buffer_size':'2097152','innodb_use_native_aio':'OFF','default_storage_engine':'InnoDB','innodb_read_io_threads':'1','innodb_write_io_threads':'2','innodb_purge_threads':'1'}
   assert all(config[k].lower()==val.lower() for k,val in expected.items()),config
   assert config['max_connections']=='10' and config['table_open_cache']=='32' and config['thread_cache_size']=='0'
  assert all(c['innodb_flush_method']=='O_DIRECT' for c in configs)
  assert d['config']['innodb_buffer_pool_load_at_startup']=='OFF'
  assert all(c['innodb_buffer_pool_dump_at_shutdown']=='OFF' and c['innodb_flush_log_at_trx_commit']==('1' if variant=='both-off' else '0') for c in configs)
  for c in configs:
   assert all(k in c for k in ['innodb_flush_method','innodb_data_file_buffering','innodb_data_file_write_through','innodb_log_file_write_through'])
   if variant=='commit0-method':assert c['innodb_flush_method'] in ['O_DIRECT_NO_FSYNC','O_DIRECT']
  assert all(c['innodb_buffer_pool_load_at_startup']=='OFF' for c in configs[1:])
  save('effective-'+arm+'.json',{'root':d['config'],'children':[v['config'] for v in d['samples']],'root_and_eight_child_assertions':'PASS'})
 else:assert not d.get('config') and all(not v.get('config') for v in d['samples'])
 events=sorted([(v['offset_ms'],1) for v in d['samples']]+[(v['offset_ms']+v['total_ms'],-1) for v in d['samples']]);active=peak=0
 for _,delta in events:active+=delta;peak=max(peak,active)
 assert active==0 and peak<=p
 if not negative:assert peak==p
 save(label+'-memory.json',{'baseline_rss_bytes':baseline,'sampled_peak_rss_bytes':max((v['rss_bytes'] for v in samples),default=None),'samples':samples,'interval_ms':20,'peak_active_children':peak})
 saved_traces=[];saved_captures=[]
 for path in sorted(traces.glob('*.json')):
  j=json.loads(path.read_text());assert not j['truncated'];dest=label+'-notify-'+path.name;(e/dest).write_bytes(path.read_bytes());saved_traces.append(dest)
 if arm=='owner' and not negative:assert len(saved_traces)==count
 for path in sorted(stacks.glob('*')):
  dest=label+'-capture-'+path.name;(e/dest).write_bytes(path.read_bytes());saved_captures.append(dest)
 records.append({'arm':arm,'variant':variant,'trace_reports':saved_traces,'capture_files':saved_captures,'parallel':p,'repetition':rep,'count':count,'negative':negative,'warmup':warmup,'preflight':preflight,'report':out.name,'memory':label+'-memory.json','process_wall_ms':wall,'returncode':code,'binary_sha256':inputs['arms'][arm]['binary_sha256']});save('records.json',records);print(label,'PASS','UPDATE max',round(max((x['update_ms'] for x in d['samples']),default=0),3),'ms','gt100',sum(x['update_ms']>100 for x in d['samples']),flush=True)

for arm in ['original','owner']:
 run(arm,8,-3,8,preflight=True);run(arm,1,-2,1,negative=True)
a=json.loads((e/'effective-original.json').read_text());b=json.loads((e/'effective-owner.json').read_text());assert a==b,'effective config mismatch'
save('preflight.json',{'result':'PASS','root_and_eight_children_identical_effective_config':True,'wrong_seed_controls':2})
for arm in ['original','owner']:run(arm,8,-1,warmup=True)
for rep,order in enumerate(plan['protocol']['pairs']):
 for arm in order:run(arm,8,rep)
save('complete.json',{'result':'COLLECTED','primary_processes':10,'primary_children':480,'preflight_processes':2,'wrong_seed_processes':2,'warmup_processes':2,'total_processes':16,'max_extra_runs':0,'controller_source_commit':inputs['controller_source_commit'],'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'peak_workspace_bytes':guard.peak,'min_free_bytes':guard.minimum_free,'not_a_frequency_estimate':True})
