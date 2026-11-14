from pathlib import Path
import os,subprocess,json,time,hashlib,resource
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence'
records=[]
for i in range(3):
 for on in ([False,True]if i%2==0 else[True,False]):
  name=f'r{i}-'+('on'if on else'off');out=E/name
  env=dict(os.environ,MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',GOMAXPROCS='8',GOGC='100',MODELCASE_TRACE=str(E/(name+'.json')))
  if on:out.mkdir();env['IPC_DIAG_DIR']=str(out)
  at=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
  with (E/(name+'.txt')).open('w')as f:p=subprocess.run([str(T/'probe'),'-test.run=^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$','-test.parallel=8'],cwd=T/'maria',env=env,stdout=f,stderr=f,timeout=180)
  after=resource.getrusage(resource.RUSAGE_CHILDREN)
  records.append(dict(name=name,code=p.returncode,wall_ms=(time.monotonic()-at)*1000,cpu_ms=((after.ru_utime-before.ru_utime)+(after.ru_stime-before.ru_stime))*1000,binary_sha256=hashlib.sha256((T/'probe').read_bytes()).hexdigest()))
  (E/'records.json').write_text(json.dumps(records,indent=2));print(name,p.returncode,flush=True)
  if p.returncode:raise RuntimeError(name)
