from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time
sys.dont_write_bytecode=True
from decompose import decompose,events
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
p=json.loads((H/'plan.json').read_text());inputs=json.loads((E/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==inputs['harness_source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
assert hashlib.sha256((T/'bin-current').read_bytes()).hexdigest()==inputs['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_DIAG','FORK_STAGE','SHOP_PARALLEL'))};env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16')
(E/'host.json').write_text(json.dumps(dict(platform=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))),indent=2)+'\n')
records=[];schedule=[]
for r in range(-1,3):
 for par in ([4,8] if r%2 else [8,4]):
  for active in ([False,True] if r%2 else [True,False]):schedule.append((r,par,active))
try:
 for repeat,par,active in schedule:
  mode='on' if active else 'off';name=f'p{par}-{mode}-r{repeat}';scratch=T/name;scratch.mkdir();trace=E/(name+'.json');diag=E/(name+'-stages.json');trace_dir=T/(name+'-timing');trace_dir.mkdir()
  local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(trace),FORK_STAGES='1' if active else '0',FORK_STAGE_PATH=str(diag),SHOP_PARALLEL=str(par))
  if active:local['MARIAMEM_TIMING_DIR']=str(trace_dir)
  before=time.monotonic()
  with (E/(name+'.txt')).open('w') as log:proc=subprocess.run([str(T/'bin-current'),f'-test.parallel={par}','-test.timeout=140s','-test.count=1'],cwd=T/'runner',env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
  data=json.loads(trace.read_text()) if trace.exists() else None;details=json.loads(diag.read_text()) if diag.exists() else None
  r=dict(name=name,parallel=par,mode=mode,repeat=repeat,exit_code=proc.returncode,process_elapsed_ms=(time.monotonic()-before)*1000,scratch_empty=not list(scratch.iterdir()),trace=data,stages=details);records.append(r)
  def save():(E/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
  save();assert proc.returncode==0 and data,(name,proc.returncode)
  m=data['meta'];ss=data['spans'];assert m['read_cases']=='50' and m['write_cases']=='20' and m['test_exit']=='0' and m['parallel']==str(par) and m['fork_cap']==str(par+1) and m['active_mappings_after']=='0' and r['scratch_empty']
  for k,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(x['kind']==k for x in ss)==n
  lanes={x['lane'] for x in ss if x['kind']=='fork'}
  if active:
   assert set(details)==lanes|{'root'}
   for lane,tr in details.items():
    assert tr['startup']['guest']['version']==1;decompose(tr)
    for op in (['api_startup','startup'] if lane=='root' else ['fork','api_startup','startup']):events(tr[op]['events'])
    if lane!='root':assert {'memory_begin','memory_ready','filesystem_begin','filesystem_ready','execute_begin','ready_response_observed','diagnostic_read_begin','diagnostic_read_end'}<=set(events(tr['startup']['events']))
  else:assert details is None
  r['accepted']=True;save();print(name,'PASS',round(data['elapsed_ms'],3),'ms',flush=True)
finally:
 (E/'completion.json').write_text(json.dumps(dict(result='COLLECTED' if len(records)==16 and all(r.get('accepted') for r in records) else 'STOPPED_INCOMPLETE',harness_source_commit=inputs['harness_source_commit'],processes=len(records),retries=0,product_changes=False),indent=2)+'\n')
