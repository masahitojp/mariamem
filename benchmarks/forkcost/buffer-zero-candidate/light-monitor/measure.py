from pathlib import Path
import os,subprocess,json,time,hashlib,resource,statistics as st
E=Path(__file__).resolve().parent;T=E.parents[1]/'temp';R=E/'runs';R.mkdir(exist_ok=True)
assert json.loads((E.parent/'validation-complete.json').read_text())['result']=='PASS'
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
for k in list(env):
 if k.startswith(('MARIAMEM_TIMING','MARIAMEM_IPC','MARIAMEM_BP_')):env.pop(k)
plan=[]
for p in (1,8):
 for rep in (-1,0,1,2):
  order=('baseline','candidate') if rep in (-1,0,2) else ('candidate','baseline')
  for v in order:
   for h in ('lifecycle','suite'):plan.append(dict(p=p,variant=v,harness=h,repetition=rep))
(E/'measurement-plan.json').write_text(json.dumps(plan,indent=2)+'\n');records=[]
for item in plan:
 p,v,h,rep=[item[k] for k in ('p','variant','harness','repetition')];name=f'{h}-p{p}-{v}-r{rep}';binary=T/(v+'-'+h);out=R/(name+'.json');cmd=[str(binary)];runenv=env.copy()
 if h=='lifecycle':cmd+=['-parallel',str(p),'-waves',str(2 if rep<0 else 6),'-out',str(out)]
 else:cmd+=['-test.parallel='+str(p),'-test.count=1','-test.timeout=120s'];runenv['MODELCASE_TRACE']=str(out)
 at=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (R/(name+'.log')).open('w') as log:r=subprocess.run(cmd,env=runenv,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 elapsed=(time.monotonic()-at)*1000;after=resource.getrusage(resource.RUSAGE_CHILDREN);assert r.returncode==0,name
 d=json.loads(out.read_text())
 if h=='lifecycle':assert d['success'] and not d['traced'] and not d['profile'] and all(c['oracle'] and c['closed'] for c in d['children'])
 else:assert (R/(name+'.log')).read_text().rstrip().endswith('PASS')
 records.append(dict(item,name=name,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),returncode=r.returncode,process_wall_ms=elapsed,cpu_user_ms=(after.ru_utime-before.ru_utime)*1000,cpu_system_ms=(after.ru_stime-before.ru_stime)*1000,minor_faults=after.ru_minflt-before.ru_minflt))
 (E/'measurement-records.json').write_text(json.dumps(records,indent=2)+'\n');print(name,round(elapsed,2),'ms',flush=True)
assert len(records)==32
(E/'measurement-complete.json').write_text(json.dumps(dict(result='PASS',processes=32,measured=24,warmups=8),indent=2)+'\n')
