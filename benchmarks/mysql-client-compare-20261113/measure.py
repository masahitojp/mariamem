from pathlib import Path
import os,subprocess,json,time,resource,sys
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100',MARIA_AUDIT_OF='1',MODELCASE_MATCHED='1');env.pop('MODELCASE_DSN',None);env.pop('IPC_DIAG_DIR',None)
arms=['pg','standard','stdlib','native']
def guard():subprocess.run([sys.executable,str(r/'worktree/scripts/experiment_disk.py'),'--work-dir',str(r),'--min-free-gib','12','--budget-gib','10'],check=True,capture_output=True)
def run(arm,p,i):
 guard();name=f'{arm}-p{p}-r{i}';e=env.copy();e.update(TRIGGERS_OFF='1',PROBE_ENGINE='pg' if arm=='pg' else 'maria',MYSQL_CLIENT_PATH=arm,LOAD_PARALLEL=str(p),MODELCASE_TRACE=str(o/f'{name}-trace.json'));binary=e['PROBE_ENGINE']
 u=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic_ns();q=subprocess.run([str(r/'temp'/f'{binary}.test'),'-test.v','-test.run','^TestInsertOnly$','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);wall=(time.monotonic_ns()-t)/1e6;v=resource.getrusage(resource.RUSAGE_CHILDREN)
 x={'name':name,'arm':arm,'parallel':p,'repeat':i,'wall_ms':wall,'user_ms':(v.ru_utime-u.ru_utime)*1000,'system_ms':(v.ru_stime-u.ru_stime)*1000,'returncode':q.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in q.stdout.splitlines())};x['cpu_ms']=x['user_ms']+x['system_ms'];rows.append(x);(o/f'{name}.output.txt').write_text(q.stdout+q.stderr);(o/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True);guard()
 if q.returncode or x['leaf_pass']!=8:raise SystemExit('stop on probe/oracle failure')
for p in [1,8]:
 for arm in arms:run(arm,p,-1)
for i in range(5):
 for p in ([1,8] if i%2==0 else [8,1]):
  order=arms[i%4:]+arms[:i%4]
  for arm in order:run(arm,p,i)
