from pathlib import Path
import os,subprocess,json,time,hashlib,resource,shutil
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';records=[]
assert shutil.disk_usage(T).free>=8*1024**3
binary_hash=hashlib.sha256((T/'probe').read_bytes()).hexdigest()
def run(name,p,arm,observe=False,phase='primary'):
 assert shutil.disk_usage(T).free>=8*1024**3
 env=dict(os.environ,MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',GOMAXPROCS='8',GOGC='100',MARIAMEM_EXPERIMENT_READ_BUFFER=str(arm),MODELCASE_TRACE=str(E/(name+'.json')))
 env.pop('IPC_DIAG_DIR',None)
 if observe:(E/name).mkdir();env['IPC_DIAG_DIR']=str(E/name)
 before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with (E/(name+'.txt')).open('w')as f:r=subprocess.run([str(T/'probe'),'-test.run=^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$',f'-test.parallel={p}'],cwd=T/'maria',env=env,stdout=f,stderr=f,timeout=180)
 wall=(time.monotonic()-at)*1000;after=resource.getrusage(resource.RUSAGE_CHILDREN);u=(after.ru_utime-before.ru_utime)*1000;s=(after.ru_stime-before.ru_stime)*1000
 records.append(dict(name=name,parallel=p,arm=arm,phase=phase,code=r.returncode,wall_ms=wall,user_ms=u,system_ms=s,cpu_ms=u+s,binary_sha256=binary_hash))
 (E/'records.json').write_text(json.dumps(records,indent=2));print(name,r.returncode,round(wall,2),flush=True)
 if r.returncode:raise RuntimeError(name)
for p in [1,8]:
 for arm in [0,1]:run(f'p{p}-warm-a{arm}',p,arm,phase='warmup')
 for i in range(5):
  for arm in ([0,1]if i%2==0 else[1,0]):run(f'p{p}-r{i}-a{arm}',p,arm)
for i in range(3):
 for arm in ([0,1]if i%2==0 else[1,0]):run(f'count-r{i}-a{arm}',8,arm,True,'counts')
print('COMPLETE',flush=True)
