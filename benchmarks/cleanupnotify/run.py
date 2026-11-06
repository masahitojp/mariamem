from pathlib import Path
import json,os,subprocess,sys,hashlib,time,platform
w=Path(__file__).resolve().parents[1];t=w/'temp';s=w/'worktree';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from experiment_disk import DiskGuard,run_guarded
save=lambda n,x:(e/n).write_text(json.dumps(x,indent=2)+'\n')
i=json.loads((e/'inputs.json').read_text());assert not (e/'records.json').exists(),'protocol already started'
assert hashlib.sha256((t/'probe').read_bytes()).hexdigest()==i['binary_sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==i['harness_source_commit'] and not subprocess.check_output(['git','status','--porcelain'],cwd=s).strip()
plan=json.loads((e/'plan.json').read_text());env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS','FORKSTAGES_','DEFAULT_SETTINGS_','ISSUE116_','ISSUE117_','UPDATE_'))};env.update(GOMAXPROCS='8',GOGC='100')
save('host.json',{'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'logical_cpus':int(subprocess.check_output(['sysctl','-n','hw.ncpu'],text=True))})
guard=DiskGuard(w,12,6);records=[]
def run(variant,rep,count=48,negative=False,warmup=False,diagnostic=False):
 p=1 if negative else 4;label=f'{variant}-r{rep}'+('-negative' if negative else '-warmup' if warmup else '-diagnostic' if diagnostic else '')
 scratch=t/'scratch'/label;scratch.mkdir(parents=True);out=e/(label+'.json');v=dict(env,TMPDIR=str(scratch),ISSUE117_VARIANT=variant)
 traces=t/'trace'/label;stacks=t/'stack'/label;traces.mkdir(parents=True);stacks.mkdir(parents=True)
 if diagnostic:v.update(ISSUE117_TRACE='1',UPDATE_NOTIFY_DIR=str(traces),UPDATE_WAIT_DIR=str(stacks))
 cmd=[str(t/'probe'),'-route','pipe','-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 started=time.monotonic()
 with (e/(label+'.log')).open('w') as log:code=run_guarded(cmd,guard,cwd=s/'benchmarks/forkcompare',env=v,output=log,timeout=120)
 d=json.loads(out.read_text());assert d['cleanup_complete'] and not any(scratch.iterdir())
 assert d['root_closed_before_forks'] and d['parallel']==p and d['route']=='pipe' and d['gomaxprocs']==8
 if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
 else:assert code==0 and d['success'] and len(d['samples'])==count and {x['index'] for x in d['samples']}==set(range(count)) and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
 for x in d['samples']:
  assert all(x[k]>=0 for k in ['retire_ms','wait_ms','close_ms','cleanup_ms'])
  assert x['retire_ms']+x['wait_ms']+x['close_ms']<=x['cleanup_ms']+.05
  if diagnostic:
   q=x['wait_trace'];assert q['success'] and q['idle_observed'] and q['checks'][-1]['active']==0
   if variant=='notify':assert q['sleep_requests']==0
  else:assert 'wait_trace' not in x
 events=sorted([(x['offset_ms'],1) for x in d['samples']]+[(x['offset_ms']+x['total_ms'],-1) for x in d['samples']]);n=peak=0
 for _,delta in events:n+=delta;peak=max(peak,n)
 assert n==0 and peak<=p
 if not negative:assert peak==p
 tracefiles=[];captures=[]
 for path in sorted(traces.glob('*.json')):
  dest=label+'-undo-'+path.name;(e/dest).write_bytes(path.read_bytes());tracefiles.append(dest)
 for path in sorted(stacks.glob('*')):
  dest=label+'-capture-'+path.name;(e/dest).write_bytes(path.read_bytes());captures.append(dest)
 rec={'variant':variant,'rep':rep,'negative':negative,'warmup':warmup,'diagnostic':diagnostic,'count':count,'report':out.name,'trace_reports':tracefiles,'capture_files':captures,'returncode':code,'process_seconds':time.monotonic()-started,'peak_active_children':peak};records.append(rec);save('records.json',records)
 if diagnostic:
  assert len(tracefiles)==count
  for f in tracefiles:assert not json.loads((e/f).read_text())['truncated'],f
 print(label,'PASS','batch',round(d['batch_ms'],2),'wait median',round(sorted(x['wait_ms'] for x in d['samples'])[len(d['samples'])//2],3),flush=True)
for variant in ['poll','notify']:run(variant,-2,1,negative=True)
for variant in ['poll','notify']:run(variant,-1,warmup=True)
for rep,variants in enumerate(plan['protocol']['ordinary_order']):
 for variant in variants:run(variant,rep)
for variant in ['poll','notify']:run(variant,0,diagnostic=True)
save('complete.json',{'result':'COLLECTED','total_processes':len(records),'primary_children_per_variant':240,'diagnostic_children_per_variant':48,'extra_repeats':0,'harness_source_commit':i['harness_source_commit'],'peak_workspace_bytes':guard.peak,'min_free_bytes':guard.minimum_free})
