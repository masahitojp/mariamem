from pathlib import Path
import os,subprocess,time,resource,json,hashlib,shutil,re
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';D=E/'campaign';D.mkdir(exist_ok=True);rows=[];start=time.monotonic()
for p in [1,8]:
 plan=[('warm',l)for l in ['baseline','candidate']]+[(str(i),l)for i in range(5)for l in (['baseline','candidate']if i%2==0 else['candidate','baseline'])]
 for iteration,label in plan:
  assert time.monotonic()-start<900 and shutil.disk_usage(T).free>=8*1024**3
  name=f'p{p}-{iteration}-{label}';env=dict(os.environ,INSERT_STAGES='0',SUM_EXPERIMENT='incremental',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',TRIGGERS_OFF='0',PROBE_ENGINE='maria',LOAD_PARALLEL=str(p),GOMAXPROCS='8',GOGC='100',MODELCASE_TRACE=str(D/(name+'-trace.json')),STAGES_FILE='')
  for k in ['PROFILE_ONLY','PROFILE_DIR','OBS_FILE','CLIENT_FILE','IPC_DIAG_DIR','MODELCASE_DSN','SAMPLE_PROFILE']:env.pop(k,None)
  b=resource.getrusage(resource.RUSAGE_CHILDREN);a=time.monotonic()
  with(D/(name+'.txt')).open('w')as f:r=subprocess.run(['/usr/bin/time','-l',str(T/(label+'.test')),'-test.v','-test.run=^TestInsertOnly$','-test.timeout=120s'],cwd=T/'maria',env=env,stdout=f,stderr=f,timeout=150)
  z=resource.getrusage(resource.RUSAGE_CHILDREN);rows.append(dict(name=name,p=p,iteration=iteration,label=label,code=r.returncode,wall_ms=(time.monotonic()-a)*1000,user_ms=(z.ru_utime-b.ru_utime)*1000,system_ms=(z.ru_stime-b.ru_stime)*1000));(D/'records.json').write_text(json.dumps(rows,indent=2));text=(D/(name+'.txt')).read_text();m=re.search(r'(\d+)\s+maximum resident set size',text);assert m;rows[-1]['maxrss_bytes']=int(m.group(1));(D/'records.json').write_text(json.dumps(rows,indent=2));print(name,r.returncode,flush=True);assert r.returncode==0
print('COMPLETE')
