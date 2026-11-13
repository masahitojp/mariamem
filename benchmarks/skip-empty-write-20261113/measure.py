from pathlib import Path
import subprocess,os,time,json,resource,sys
r=Path(__file__).resolve().parents[1];out=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100')
def guard():
 subprocess.run([sys.executable,str(r/'worktree/scripts/experiment_disk.py'),'--work-dir',str(r),'--min-free-gib','12','--budget-gib','10'],check=True,capture_output=True)
def run(name,arm,observe=False):
 guard();e=env.copy();e['MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE']='1' if arm=='candidate' else '0';e['MODELCASE_TRACE']=str(out/f'{name}-trace.json')
 if observe:
  directory=out/f'{name}-ipc';directory.mkdir();e['IPC_DIAG_DIR']=str(directory)
 start_usage=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic_ns()
 p=subprocess.run([str(r/'temp/maria.test'),'-test.v','-test.parallel=8','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130)
 ms=(time.monotonic_ns()-t)/1e6;end_usage=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'name':name,'arm':arm,'observe':observe,'wall_ms':ms,'user_ms':(end_usage.ru_utime-start_usage.ru_utime)*1000,'system_ms':(end_usage.ru_stime-start_usage.ru_stime)*1000,'returncode':p.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines())};row['cpu_ms']=row['user_ms']+row['system_ms'];rows.append(row);(out/f'{name}.output.txt').write_text(p.stdout+p.stderr);(out/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
 guard()
 if row['returncode'] or row['leaf_pass']!=70:raise SystemExit('correctness failure; stop, retain all observations')
 if observe:
  ds=[json.loads(f.read_text()) for f in directory.glob('db-*.json')]
  if len(ds)!=22 or any(x['exit_error'] for x in ds):raise SystemExit('joined guest completion mismatch')
for arm in ['baseline','candidate']:run('warmup-'+arm,arm)
for i in range(5):
 for arm in (['baseline','candidate'] if i%2==0 else ['candidate','baseline']):run(f'primary-{arm}-{i}',arm)
for i in range(3):
 for arm in (['baseline','candidate'] if i%2==0 else ['candidate','baseline']):run(f'count-{arm}-{i}',arm,True)
