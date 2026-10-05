"""Bounded experiment mechanics; use under the pinned workspace runner."""
import os,json,resource,subprocess,sys,time,signal
from pathlib import Path
R=Path(__file__).resolve().parents[3];T=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']);E=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
sys.path.insert(0,str(Path(os.environ['MARIAMEM_TOOLING_REPO'])/'scripts'))
from experiment_disk import DiskGuard
G=DiskGuard(T.parent,16,6);G.check()
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0')
for k in ('MARIAMEM_RUNTIME','MARIAMEM_NATIVE_DIR','MARIAMEM_GENERATED_HOST','MARIAMEM_GENERATED_GUEST'):env.pop(k,None)
record={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'platform':sys.platform,'phases':[],'budget':{'disk_gib':6,'min_free_gib':16,'rss_gib':6,'physical_or_pss_gib':8,'cpu_soft_hard_s':[180,200],'fd':256}}
def save():
 record['disk']=G.check();(E/'campaign.json').write_text(json.dumps(record,indent=2)+'\n')
def limits():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(180,200));resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
def children(pid):
 pairs=[tuple(map(int,x.split())) for x in subprocess.check_output(['ps','-A','-o','pid=,ppid='],text=True).splitlines() if len(x.split())==2];ids={pid}
 for _ in pairs:
  n=len(ids);ids.update(a for a,b in pairs if b in ids)
  if n==len(ids):break
 return ids
helper=T/'process-cost'
def run(name,args,cwd=R,timeout=600,extras=None,allow_budget=False):
 print('RUN',name,flush=True);row={'name':name,'peak_rss_bytes':0,'peak_physical_or_pss_bytes':0};record['phases'].append(row);save();start=time.monotonic();stop=None
 with (E/(name+'.log')).open('w') as log:
  p=subprocess.Popen(list(map(str,args)),cwd=cwd,env=dict(env,**(extras or {})),stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits)
  try:
   while p.poll() is None:
    G.check()
    if helper.exists() and str(args[0])!='cc':
     counters=json.loads(subprocess.check_output([str(helper),*map(str,children(p.pid))],text=True))
     rss=sum(v.get('rss_bytes',0) for v in counters.values());physical=sum(v.get('primary_bytes',0) for v in counters.values())
     row['peak_rss_bytes']=max(rss,row['peak_rss_bytes']);row['peak_physical_or_pss_bytes']=max(physical,row['peak_physical_or_pss_bytes'])
     if rss>6*(1<<30) or physical>8*(1<<30):stop='resource budget';break
    if time.monotonic()-start>timeout:stop='timeout';break
    time.sleep(.2)
  finally:
   if p.poll() is None:
    ids=children(p.pid)
    for pid in sorted(ids,reverse=True):
     try:os.kill(pid,signal.SIGTERM)
     except ProcessLookupError:pass
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:
     for pid in ids:
      try:os.kill(pid,signal.SIGKILL)
      except ProcessLookupError:pass
     p.wait()
 row.update(exit_code=p.returncode,stop=stop,seconds=time.monotonic()-start);save();print('END',name,p.returncode,stop,flush=True)
 if p.returncode or stop:
  if allow_budget and stop=='resource budget':return False
  raise RuntimeError(name+' failed; log retained')
 return True
