from pathlib import Path
import hashlib,json,os,platform,subprocess,time
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
p=json.loads((H/'plan.json').read_text());inputs=json.loads((E/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==inputs['harness_source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
assert hashlib.sha256((T/'bin-current').read_bytes()).hexdigest()==inputs['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_DIAG'))};env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16')
(E/'host.json').write_text(json.dumps(dict(platform=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))),indent=2)+'\n')
records=[]
try:
 for name in p['processes']:
  scratch=T/name;scratch.mkdir();trace=E/(name+'.json');diag=E/(name+'-diagnostics.json');active=name.startswith('diagnostic')
  local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(trace),SAMPLE_DIAG='1' if active else '0',SAMPLE_DIAG_PATH=str(diag))
  before=time.monotonic()
  with (E/(name+'.txt')).open('w') as log:proc=subprocess.run([str(T/'bin-current'),'-test.parallel=8','-test.timeout=140s','-test.count=1'],cwd=T/'runner',env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
  data=json.loads(trace.read_text()) if trace.exists() else None;details=json.loads(diag.read_text()) if diag.exists() else None
  r=dict(name=name,exit_code=proc.returncode,process_elapsed_ms=(time.monotonic()-before)*1000,scratch_empty=not list(scratch.iterdir()),trace=data,diagnostics=details);records.append(r)
  def save():(E/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
  save();assert proc.returncode==0 and data and details,(name,proc.returncode)
  m=data['meta'];ss=data['spans'];assert m['read_cases']=='50' and m['write_cases']=='20' and m['test_exit']=='0' and m['parallel']=='8' and m['fork_cap']=='9' and m['active_mappings_after']=='0' and r['scratch_empty']
  for k,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(x['kind']==k for x in ss)==n
  ds=details['records'] or [];assert len(ds)==(21 if active else 0)
  if active:
   assert len({x['lane'] for x in ds})==21
   for x in ds:
    assert not x.get('error')
    for k,n in [('begin',1),('prepare_order',1),('prepare_item',1),('prepare_stock',1),('order_insert',40),('item_insert',100),('stock_update',100),('commit',1),('statement_close',3)]:assert len(x['ops_ms'][k])==n
  r['accepted']=True;save();print(name,'PASS',round(data['elapsed_ms'],3),'ms',flush=True)
finally:
 (E/'completion.json').write_text(json.dumps(dict(result='COLLECTED' if len(records)==4 and all(r.get('accepted') for r in records) else 'STOPPED_INCOMPLETE',harness_source_commit=inputs['harness_source_commit'],processes=len(records),retries=0,product_changes=False),indent=2)+'\n')
