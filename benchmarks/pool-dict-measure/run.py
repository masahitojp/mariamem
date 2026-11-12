"""Fixed30 suites; preserve every observation and stop on failed correctness/cleanup."""
from pathlib import Path
import hashlib,json,os,platform,re,subprocess,time
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S).strip()
rows=[]
def dump(p,x):p.write_text(json.dumps(x,separators=(',',':'))+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_','FORK_STAGE','SHOP_','TIMER_','ANALYZE_'))}
env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',FORK_STAGES='0')
plan={'origin':'7de45ac19718f37d1552824acfd6477dea6caf17','workload':'shop70 Pipe16MiB/read1 cap=P+1','warmup_suites':4,'primary_suites':20,'secondary_suites':6,'total':30,'measurement_retries':0}
dump(E/'measurement-plan.json',plan)
dump(E/'host.json',{'platform':platform.platform(),'go':'go1.26.10','cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))})

def execute(arm,mode,p,repeat):
 name=f'{mode}-p{p}-r{repeat}-{arm}';d=T/name;d.mkdir();scratch=d/'scratch';scratch.mkdir()
 kind='phases' if mode=='phases' else 'off';binary=T/(arm+'-'+kind+'.test')
 pin=json.loads((E/(arm+'-'+kind+'-runner.json')).read_text());assert sha(binary)==pin['binary_sha256']
 local=dict(env,SHOP_PARALLEL=str(p),TMPDIR=str(scratch),MODELCASE_TRACE=str(d/'trace.json'))
 if mode=='phases':local.update(ISSUE88_SAMPLE_PHASES='1',ISSUE68_CAPTURE='0',ISSUE68_CONTROL='0',SAMPLE_PHASES_OUT=str(d/'sql.json'))
 start=time.monotonic()
 with (d/'console.txt').open('w') as log:
  result=subprocess.run(['/usr/bin/time','-l',binary,f'-test.parallel={p}','-test.timeout=140s','-test.count=1'],cwd=T/arm/'tests/timer_calibration/runner',env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 elapsed=(time.monotonic()-start)*1000
 if result.returncode:raise RuntimeError(name+' FAILED: '+(d/'console.txt').read_text()[-2500:])
 trace=json.loads((d/'trace.json').read_text());m=trace['meta'];spans=trace['spans']
 for k,v in {'route':'Pipe','read_cases':'50','write_cases':'20','test_exit':'0','parallel':str(p),'fork_cap':str(p+1),'active_mappings_after':'0','innodb_buffer_pool_size':'16777216','innodb_read_io_threads':'1'}.items():assert m[k]==v,(name,k,m)
 for k,n in [('fork',21),('sample',21),('read',50),('write',20)]:assert sum(s['kind']==k for s in spans)==n,(name,k)
 assert not list(scratch.iterdir()),name
 text=(d/'console.txt').read_text()
 rss=int(re.search(r'(?m)^\s*(\d+)\s+maximum resident set size$',text).group(1))
 r={'name':name,'arm':arm,'mode':mode,'parallel':p,'repeat':repeat,'process_wall_ms':elapsed,'rss_bytes':rss,'trace':trace,'exit_code':result.returncode,'scratch_empty':True,'binary_sha256':pin['binary_sha256']}
 if mode=='phases':
  r['loaders']=json.loads((d/'sql.json').read_text());assert len(r['loaders'])==21
  for sample in r['loaders']:
   dd=sample['durations_us'];assert len(dd['prepare'])==3 and len(dd['order_insert'])==40 and len(dd['item_insert'])==len(dd['stock_update'])==100 and len(dd['commit'])==1
  assert not (d/'captures').exists()
 rows.append(r);dump(E/'observations.json',rows)
 print(name,'PASS',round(trace['elapsed_ms'],2),'ms; sample>100ms',sum(s['kind']=='sample' and s['end_ms']-s['start_ms']>100 for s in spans),flush=True)
try:
 for p in (4,8):
  for arm in ('baseline','candidate'):execute(arm,'warmup',p,0)
 for repeat in range(1,6):
  for p in ((4,8) if repeat%2 else (8,4)):
   for arm in (('baseline','candidate') if repeat%2 else ('candidate','baseline')):execute(arm,'off',p,repeat)
 for repeat in range(1,4):
  for arm in (('baseline','candidate') if repeat%2 else ('candidate','baseline')):execute(arm,'phases',8,repeat)
finally:
 dump(E/'observations.json',rows)
 dump(E/'measurement-completion.json',{'result':'COMPLETE' if len(rows)==30 else 'INCOMPLETE','accepted_suites':len(rows),'measurement_retries':0,'adoption':False})
