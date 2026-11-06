from pathlib import Path
import subprocess,sys,json,hashlib,os,time,platform
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((e/'inputs.json').read_text());plan=json.loads((b/'plan.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['harness_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert sha(b/'plan.json')==inputs['plan_sha256']
for v,i in inputs['binaries'].items():assert sha(t/('bin-'+v))==i['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_','PYTEST'))}
env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,7);records=[]
def run(variant,mode,p,rep,kind='primary',count=48,negative=False):
 name=f'{variant}-{mode}-p{p}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists(),name
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch))
 if variant=='diagnostic':
  trace=t/'trace'/name;trace.mkdir(parents=True);v['UPDATE_NOTIFY_DIR']=str(trace)
 command=[str(t/('bin-'+variant)),'-mode',mode,'-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 at=time.monotonic()
 with (e/(name+'.txt')).open('w') as log:code=run_guarded(command,guard,cwd=b,env=v,output=log,timeout=190)
 external=(time.monotonic()-at)*1000
 r=json.loads(out.read_text());assert r['cleanup'] and not list(scratch.iterdir()),(name,'cleanup')
 assert r['mode']==mode and r['parallel']==p and r['count']==count and r['gomaxprocs']==8
 assert 0<r['max_active']<=p and all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 assert r['resolved_max_forks']==(p if mode=='fork' else 0)
 if negative:assert code==1 and not r['success'] and 'pristine oracle' in r['error'],(name,code,r)
 else:
  assert code==0 and r['success'] and len(r['samples'])==count,(name,code,r)
  assert {x['index'] for x in r['samples']}==set(range(count))
  assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
  assert '12.3.3' in r['samples'][0]['version']
 for x in r['samples']:
  names=[z['name'] for z in x['spans']];assert len(names)==len(set(names))
  assert all(x['begin_ms']<=z['begin_ms']<=z['end_ms']<=x['end_ms'] for z in x['spans'])
  if not negative:assert {'start_or_fork','connect','select1','count_sum','update','verify_update','retire','close'}<=set(names) and ('seed' in names)==(mode=='fresh')
 tracefiles=[]
 if variant=='diagnostic':
  for path in sorted(trace.glob('*.json')):
   j=json.loads(path.read_text());assert not j['truncated']
   target=name+'-undo-'+path.name;(e/target).write_bytes(path.read_bytes());tracefiles.append(target)
  assert len(tracefiles)==count,(name,len(tracefiles))
 rec={'variant':variant,'mode':mode,'parallel':p,'rep':rep,'kind':kind,'negative':negative,'count':count,'report':out.name,'trace_reports':tracefiles,'exit_code':code,'external_process_ms':external}
 records.append(rec);(e/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,'expected FAIL' if negative else 'PASS','suite',round(r['suite_ms'],2),'batch',round(r['batch_ms'],2),flush=True)
for variant in ['baseline','current']:
 for mode in ['fresh','fork']:
  run(variant,mode,1,-2,'pilot',2)
  run(variant,mode,1,-2,'negative',1,True)
for mode in ['fresh','fork']:
 for p in [1,4]:
  for variant in ['baseline','current']:run(variant,mode,p,-1,'warmup')
cells=[('fresh',1),('fork',1),('fresh',4),('fork',4)]
for rep in range(5):
 ordered=cells[rep%4:]+cells[:rep%4]
 for mode,p in ordered:
  ordinal=cells.index((mode,p))
  variants=['baseline','current'] if (rep+ordinal)%2==0 else ['current','baseline']
  for variant in variants:run(variant,mode,p,rep)
for mode in ['fresh','fork']:run('diagnostic',mode,4,0,'diagnostic')
assert len(records)==58
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','total_processes':58,'primary_processes':40,'primary_pairs_per_cell':5,'extra_repetitions':0,'harness_source_commit':inputs['harness_source_commit'],'peak_workspace_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free},indent=2)+'\n')
