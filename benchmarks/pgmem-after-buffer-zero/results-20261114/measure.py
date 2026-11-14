from pathlib import Path
import os,sys,subprocess,json,time,hashlib,resource,shutil,signal,threading
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp'
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from experiment_disk import DiskGuard
from experiment_workspace import exclusive
R=E/'runs';R.mkdir(exist_ok=False)
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
for key in list(env):
 if key.startswith(('MARIAMEM_TIMING','MARIAMEM_IPC','MARIAMEM_BP_','FORKCOST_','FORKSTAGES_')) or key=='MODELCASE_DSN':env.pop(key)
records=[]
def run(name,cmd,runenv,output,negative=False):
 before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with (R/(name+'.txt')).open('w') as log:
  p=subprocess.Popen(cmd,env=runenv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  exited=[]
  def wait_child():
   p.wait();exited.append(time.monotonic())
  waiter=threading.Thread(target=wait_child);waiter.start()
  try:
   while not exited:
    if time.monotonic()-at>150 or shutil.disk_usage(X).free<8*1024**3:raise RuntimeError('process timeout/free-space reserve')
    time.sleep(.1)
  finally:
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 waiter.join()
 elapsed=1000*(exited[0]-at);after=resource.getrusage(resource.RUSAGE_CHILDREN)
 assert (p.returncode!=0)==negative,(name,p.returncode)
 d=json.loads(output.read_text())
 if 'samples' in d:
  assert d['success']!=negative and d['cleanup_complete'],(name,d)
  if not negative:assert len(d['samples'])==48 and all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
 else:
  assert not negative and (R/(name+'.txt')).read_text().rstrip().endswith('PASS'),name
  assert len([s for s in d['spans'] if s['name']=='reader_fork'])==1
 records.append({'name':name,'returncode':p.returncode,'negative_control':negative,'process_wall_ms':elapsed,'cpu_user_ms':1000*(after.ru_utime-before.ru_utime),'cpu_system_ms':1000*(after.ru_stime-before.ru_stime),'minor_faults':after.ru_minflt-before.ru_minflt,'binary_sha256':hashlib.sha256(Path(cmd[0]).read_bytes()).hexdigest()})
 (E/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,round(elapsed,2),'ms',flush=True)
with exclusive(X):
 guard=DiskGuard(X,min_free_gib=8,budget_gib=16);initial=guard.check();at=time.monotonic()
 for backend in ('mariamem','pgmem'):
  name=backend+'-negative';out=R/(name+'.json');run(name,[str(T/'bin'/(backend+'-lifecycle')),'-parallel','1','-count','2','-route','pipe','-corrupt-seed','-out',str(out)],env,out,negative=True)
 matrix=[]
 for parallel in (1,4,8):
  for rep in (-1,0,1,2):
   order=('mariamem','pgmem') if rep in (-1,0,2) else ('pgmem','mariamem')
   for backend in order:
    for harness in ('lifecycle','suite'):matrix.append({'parallel':parallel,'repetition':rep,'backend':backend,'harness':harness})
 (E/'matrix.json').write_text(json.dumps(matrix,indent=2)+'\n')
 for cell in matrix:
  p,rep,b,h=[cell[k] for k in ('parallel','repetition','backend','harness')]
  assert time.monotonic()-at<900,'matrix timeout'
  name=f'{b}-{h}-p{p}-r{rep}';out=R/(name+'.json');cmd=[str(T/'bin'/(b+'-'+h))];renv=env.copy()
  if h=='lifecycle':cmd+=['-parallel',str(p),'-count','48','-route','pipe','-out',str(out)]
  else:cmd+=['-test.parallel='+str(p),'-test.count=1','-test.timeout=120s'];renv['MODELCASE_TRACE']=str(out)
  run(name,cmd,renv,out)
 final=guard.check()
 (E/'runtime-budget.json').write_text(json.dumps({'before':initial,'after':final,'recursive_scans_during_runtime':0,'processes':len(records),'measured':36,'warmups':12,'negative_controls':2},indent=2)+'\n')
 (E/'complete.json').write_text(json.dumps({'result':'PASS','processes':len(records),'measured':36,'warmups':12,'negative_controls':2},indent=2)+'\n')
