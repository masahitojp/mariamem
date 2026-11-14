from pathlib import Path
import os,subprocess,json,time,hashlib,resource,shutil
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';records=[];began=time.monotonic()
assert shutil.disk_usage(T).free>=8*1024**3
binary_hash=hashlib.sha256((T/'probe').read_bytes()).hexdigest()
def run(name,p,arm,phase):
 assert time.monotonic()-began<900
 assert shutil.disk_usage(T).free>=8*1024**3
 env=dict(os.environ,MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',GOMAXPROCS='8',GOGC='100',LOAD_PARALLEL=str(p),PROBE_ENGINE='maria',TRIGGERS_OFF='0',INSERT_STAGES=str(arm),STAGES_FILE=str(E/(name+'-stages.json')),MODELCASE_TRACE=str(E/(name+'-trace.json')))
 for k in ['IPC_DIAG_DIR','SAMPLE_PROFILE','MODELCASE_DSN']:env.pop(k,None)
 before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with (E/(name+'.txt')).open('w')as f:r=subprocess.run([str(T/'probe'),'-test.v','-test.run=^TestInsertOnly$',f'-test.parallel={p}','-test.timeout=120s'],cwd=T/'maria',env=env,stdout=f,stderr=f,timeout=150)
 wall=(time.monotonic()-at)*1000;after=resource.getrusage(resource.RUSAGE_CHILDREN);u=(after.ru_utime-before.ru_utime)*1000;s=(after.ru_stime-before.ru_stime)*1000
 row=dict(name=name,parallel=p,arm=arm,phase=phase,code=r.returncode,wall_ms=wall,user_ms=u,system_ms=s,cpu_ms=u+s,binary_sha256=binary_hash);records.append(row)
 (E/'records.json').write_text(json.dumps(records,indent=2));print(name,r.returncode,round(wall,2),flush=True)
 if r.returncode:raise RuntimeError(name)
 obs=json.loads((E/(name+'-stages.json')).read_text())
 if arm:
  assert len(obs)==8,(name,'modules',len(obs))
  for m in obs:
   assert len(m['records'])==100,(name,'count',len(m['records']))
   ids=set()
   for e in m['records']:
    assert e['ID'] not in ids;ids.add(e['ID'])
    assert e['Counts']==[1]*7,(name,'markers',e)
    assert all(a<=b for a,b in zip(e['T'],e['T'][1:])),(name,'order',e)
    assert e['Writes']==1,(name,'writes',e)
    assert 0<=e['WriteNS']<=e['T'][6]-e['T'][5],(name,'write range',e)
 else:assert obs==[]
for p in [1,8]:
 for arm in [0,1]:run(f'p{p}-warm-a{arm}',p,arm,'warmup')
 for i in range(3):
  for arm in ([0,1]if i%2==0 else[1,0]):run(f'p{p}-r{i}-a{arm}',p,arm,'primary')
print('COMPLETE',flush=True)
