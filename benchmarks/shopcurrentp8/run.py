"""Fixed five-round P8 comparison; setup and final public cleanup included."""
from pathlib import Path
import hashlib,json,os,platform,subprocess,time
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
p=json.loads((H/'plan.json').read_text());inputs=json.loads((E/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==inputs['harness_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
for arm,b in inputs['binaries'].items():assert hashlib.sha256((T/('bin-'+arm)).read_bytes()).hexdigest()==b['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_'))};env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16')
(E/'host.json').write_text(json.dumps(dict(platform=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))),indent=2)+'\n')
records=[]
try:
 for repeat in range(-1,5):
  arms=p['arms'];order=arms if repeat<0 else arms[repeat%3:]+arms[:repeat%3]
  for arm in order:
   name=f'{arm}-r{repeat}';scratch=T/name;scratch.mkdir();trace=E/(name+'.json')
   local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(trace))
   before=time.monotonic()
   with (E/(name+'.txt')).open('w') as log:
    proc=subprocess.run([str(T/('bin-'+arm)),'-test.parallel=8','-test.timeout=140s','-test.count=1'],cwd=T/(arm+'-runner'),env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
   data=json.loads(trace.read_text()) if trace.exists() else None
   r=dict(arm=arm,repeat=repeat,exit_code=proc.returncode,process_elapsed_ms=(time.monotonic()-before)*1000,scratch_empty=not list(scratch.iterdir()),trace=data)
   records.append(r);(E/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
   assert proc.returncode==0 and data,(name,proc.returncode)
   meta=data['meta'];spans=data['spans']
   assert meta['read_cases']=='50' and meta['write_cases']=='20' and meta['test_exit']=='0'
   assert meta['parallel']=='8' and meta['fork_cap']=='9'
   assert sum(s['kind']=='read' for s in spans)==50 and sum(s['kind']=='write' for s in spans)==20 and sum(s['kind']=='fork' for s in spans)==21
   if arm!='pgmem':assert meta['active_mappings_after']=='0' and r['scratch_empty']
   r['accepted']=True
   (E/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
   print(name,'PASS',round(data['elapsed_ms'],3),'ms',flush=True)
finally:
 (E/'completion.json').write_text(json.dumps(dict(result='COLLECTED' if len(records)==18 and all(r.get('accepted',False) for r in records) else 'STOPPED_INCOMPLETE',harness_source_commit=inputs['harness_source_commit'],processes=len(records),primary_processes=sum(r['repeat']>=0 for r in records),retries=0,product_changes=False),indent=2)+'\n')
