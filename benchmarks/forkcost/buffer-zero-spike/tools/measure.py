from pathlib import Path
import subprocess,os,json,time,resource,hashlib
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';R=E/'runs';R.mkdir(exist_ok=True)
assert json.loads((E/'correctness-primary-complete.json').read_text())['result']=='PASS'
assert json.loads((E/'extra-validation-complete.json').read_text())['result']=='PASS'
assert json.loads((E/'negative-descriptor.json').read_text())['explicit_check_marker']
assert json.loads((T/'native/development.json').read_text())['result']=='UNQUALIFIED'
base=os.environ.copy();base.update(GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
for k in list(base):
 if k.startswith(('MARIAMEM_TIMING','MARIAMEM_IPC','MARIAMEM_BP_')):base.pop(k)
plan=[]
for p in (1,8):
 for v in ('canonical','baseline','metadata'):
  for h in ('probe','suite'):plan.append({'p':p,'variant':v,'harness':h,'repetition':-1})
 for rep in range(3):
  order=[('canonical','baseline','metadata'),('metadata','canonical','baseline'),('baseline','metadata','canonical')][rep]
  for v in order:
   for h in ('probe','suite'):plan.append({'p':p,'variant':v,'harness':h,'repetition':rep})
(E/'measurement-plan.json').write_text(json.dumps(plan,indent=2)+'\n');records=[]
for item in plan:
 p,v,h,rep=[item[k] for k in ('p','variant','harness','repetition')];name=f'{h}-p{p}-{v}-r{rep}';binary=T/(('canonical' if v=='canonical' else 'spike')+'-'+h);env=base.copy()
 if v!='canonical':env['MARIAMEM_BP_ZERO_MODE_INTERNAL']=v
 out=R/(name+'.json');log=R/(name+'.log');cmd=[str(binary)]
 if h=='probe':cmd+=['-parallel',str(p),'-waves',str(2 if rep<0 else 6),'-out',str(out)]
 else:cmd+=['-test.parallel='+str(p),'-test.count=1','-test.timeout=120s'];env['MODELCASE_TRACE']=str(out)
 before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with log.open('w') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=140)
 elapsed=(time.monotonic()-at)*1000;after=resource.getrusage(resource.RUSAGE_CHILDREN);d=json.loads(out.read_text());assert r.returncode==0,log.read_text()
 if h=='probe':assert d['success'] and all(c['oracle'] and c['closed'] for c in d['children'])
 else:assert log.read_text().rstrip().endswith('PASS')
 row=dict(item,name=name,returncode=r.returncode,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),process_wall_ms=elapsed,cpu_user_ms=(after.ru_utime-before.ru_utime)*1000,cpu_system_ms=(after.ru_stime-before.ru_stime)*1000,minor_faults=after.ru_minflt-before.ru_minflt,major_faults=after.ru_majflt-before.ru_majflt)
 records.append(row);(E/'measurement-records.json').write_text(json.dumps(records,indent=2)+'\n');print(name,round(elapsed,2),'ms',flush=True)
(E/'measurement-complete.json').write_text(json.dumps({'result':'PASS','processes':len(records),'measured_processes':sum(r['repetition']>=0 for r in records),'warmups':sum(r['repetition']<0 for r in records)},indent=2)+'\n')
