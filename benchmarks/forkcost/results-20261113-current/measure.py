import os,json,subprocess,pathlib,time
E=pathlib.Path(__file__).resolve().parent; W=E.parent; R=E/'runs';R.mkdir(exist_ok=True)
env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
for k in list(env):
 if k.startswith('MARIAMEM_TIMING') or k.startswith('MARIAMEM_IPC'):env.pop(k)
plan=[]
for p in (1,8):
 for t in (False,True):plan.append((f'warm-p{p}-t{int(t)}',p,t,2,False,False))
 plan.append((f'pilot-p{p}',p,True,1,False,False))
 for r in range(3):
  for t in ((False,True) if r%2==0 else (True,False)):plan.append((f'main-p{p}-r{r}-t{int(t)}',p,t,6,False,False))
plan.append(('negative',1,True,1,False,True))
for p in (1,8):plan.append((f'profile-p{p}',p,False,8,True,False))
(E/'plan.json').write_text(json.dumps(plan,indent=2))
for name,p,t,w,prof,neg in plan:
 cmd=[str(W/'temp'/('observed' if t else 'canonical')),'-parallel',str(p),'-waves',str(w),'-out',str(R/(name+'.json'))]
 if t:cmd+=['-traced']
 if prof:cmd+=['-profile']
 if neg:cmd+=['-negative']
 start=time.time();r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=135)
 (R/(name+'.log')).write_text(r.stdout)
 d=json.loads((R/(name+'.json')).read_text())
 assert (r.returncode==1 and not d['success'] and 'want1001' in d['error']) if neg else (r.returncode==0 and d['success']),r.stdout
 assert all(c['closed'] for c in d['children'])
 if not neg:assert all(c['oracle'] for c in d['children'])
 print(name,round(time.time()-start,2),r.stdout.strip(),flush=True)
