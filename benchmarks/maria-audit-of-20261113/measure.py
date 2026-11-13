from pathlib import Path
import os,subprocess,json,time,resource,sys
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100');env.pop('MODELCASE_DSN',None);env.pop('IPC_DIAG_DIR',None)
orders=[['pg-official','maria-of','maria-old'],['maria-old','maria-of','pg-official'],['maria-of','maria-old','pg-official'],['pg-official','maria-old','maria-of'],['maria-of','pg-official','maria-old']]
def guard():subprocess.run([sys.executable,str(r/'worktree/scripts/experiment_disk.py'),'--work-dir',str(r),'--min-free-gib','12','--budget-gib','10'],check=True,capture_output=True)
def run(arm,i):
 guard();e=env.copy();e['MARIA_AUDIT_OF']='1' if arm=='maria-of' else '0';e['MODELCASE_TRACE']=str(o/f'{arm}-{i}-trace.json');binary='pg' if arm=='pg-official' else 'maria'
 u=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic_ns();p=subprocess.run([str(r/'temp'/f'{binary}.test'),'-test.v','-test.parallel=8','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);wall=(time.monotonic_ns()-t)/1e6;v=resource.getrusage(resource.RUSAGE_CHILDREN)
 x={'arm':arm,'repeat':i,'wall_ms':wall,'user_ms':(v.ru_utime-u.ru_utime)*1000,'system_ms':(v.ru_stime-u.ru_stime)*1000,'returncode':p.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines())};x['cpu_ms']=x['user_ms']+x['system_ms'];rows.append(x);(o/f'{arm}-{i}.output.txt').write_text(p.stdout+p.stderr);(o/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True);guard()
 if p.returncode or x['leaf_pass']!=70:raise SystemExit('stop on correctness failure')
for a in orders[0]:run(a,-1)
for i,order in enumerate(orders):
 for a in order:run(a,i)
