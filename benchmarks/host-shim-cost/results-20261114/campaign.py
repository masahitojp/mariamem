from pathlib import Path
import os,time,subprocess,json,resource,shutil
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';D=E/'campaign188';D.mkdir(exist_ok=True);rows=[];begin=time.monotonic()
def run(n,p,a,profile=False):
 assert time.monotonic()-begin<1200 and shutil.disk_usage(T).free>=8*1024**3
 env=dict(os.environ,INSERT_STAGES=str(a),SUM_EXPERIMENT='incremental',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',TRIGGERS_OFF='0',PROBE_ENGINE='maria',LOAD_PARALLEL=str(p),GOMAXPROCS='8',GOGC='100',MODELCASE_TRACE=str(D/(n+'-trace.json')),STAGES_FILE=str(D/(n+'-stages.json')),OBS_FILE=str(D/(n+'-events.json')),CLIENT_FILE=str(D/(n+'-clients.json')))
 for k in ['PROFILE_ONLY','PROFILE_DIR','IPC_DIAG_DIR','MODELCASE_DSN']:env.pop(k,None)
 if profile:
  (D/n).mkdir();env.update(PROFILE_ONLY='1',PROFILE_DIR=str(D/n),CLIENT_FILE='')
 b=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
 with(D/(n+'.txt')).open('w')as f:r=subprocess.run([str(T/'probe'),'-test.v','-test.run=^TestInsertOnly$','-test.timeout=180s'],cwd=T/'maria',env=env,stdout=f,stderr=f,timeout=200)
 z=resource.getrusage(resource.RUSAGE_CHILDREN);rows.append(dict(name=n,p=p,arm=a,profile=profile,code=r.returncode,wall_ms=(time.monotonic()-start)*1000,cpu_ms=(z.ru_utime+z.ru_stime-b.ru_utime-b.ru_stime)*1000));(D/'records.json').write_text(json.dumps(rows,indent=2));print(n,r.returncode,flush=True);assert r.returncode==0
 if a:
  subprocess.run(['python3',str(E/'reduce188.py'),str(D),n],check=True)
for p in [1,8]:
 for a in [0,1]:run(f'p{p}-warm-a{a}',p,a)
 for i in range(3):
  for a in ([0,1]if i%2==0 else[1,0]):run(f'p{p}-r{i}-a{a}',p,a)
for i in range(3):run(f'profile-{i}',8,0,True)
