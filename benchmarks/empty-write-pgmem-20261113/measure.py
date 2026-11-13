from pathlib import Path
import os,subprocess,json,time,resource,sys
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100');env.pop('IPC_DIAG_DIR',None)
orders=[['pgmem','baseline','candidate'],['candidate','baseline','pgmem'],['baseline','candidate','pgmem'],['pgmem','candidate','baseline'],['candidate','pgmem','baseline']]
def guard():subprocess.run([sys.executable,str(r/'worktree/scripts/experiment_disk.py'),'--work-dir',str(r),'--min-free-gib','12','--budget-gib','10'],check=True,capture_output=True)
def run(arm,repeat):
 guard();e=env.copy();e['MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE']='1' if arm=='candidate' else '0';e['MODELCASE_TRACE']=str(o/f'{arm}-{repeat}-trace.json');binary='pgmem' if arm=='pgmem' else 'maria'
 u=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic_ns();p=subprocess.run([str(r/'temp'/f'{binary}.test'),'-test.v','-test.parallel=8','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);wall=(time.monotonic_ns()-t)/1e6;v=resource.getrusage(resource.RUSAGE_CHILDREN)
 x={'arm':arm,'repeat':repeat,'wall_ms':wall,'user_ms':(v.ru_utime-u.ru_utime)*1000,'system_ms':(v.ru_stime-u.ru_stime)*1000,'returncode':p.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines())};x['cpu_ms']=x['user_ms']+x['system_ms'];rows.append(x);(o/f'{arm}-{repeat}.output.txt').write_text(p.stdout+p.stderr);(o/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True);guard()
 if x['returncode'] or x['leaf_pass']!=70:raise SystemExit('correctness failure, stop and retain all')
for arm in ['pgmem','baseline','candidate']:run(arm,-1)
for i,order in enumerate(orders):
 for arm in order:run(arm,i)
