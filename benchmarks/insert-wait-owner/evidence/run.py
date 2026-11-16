from pathlib import Path
import os,sys,subprocess,json,time,hashlib
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence'
sys.path.insert(0,str(r/'scripts'));from experiment_disk import DiskGuard
g=DiskGuard(w,8,6);inputs=json.loads((e/'inputs.json').read_text());assert hashlib.sha256((t/'observe.test').read_bytes()).hexdigest()==inputs['binary_sha256'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
for k in ['GODEBUG','MODELCASE_DSN','SKIP_READ_BODY','TRIGGERS_OFF','SUM_EXPERIMENT','SAMPLE_PROFILE','PROFILE_DIR','INSERT_STAGES','PROFILE_ONLY','RESPONSE_PIPE']:env.pop(k,None)
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';deadline=time.monotonic()+300;results=[]
for i in range(8):
 g.check();assert time.monotonic()<deadline
 with (e/f'run-{i}.txt').open('w')as f:q=subprocess.run([str(t/'observe.test'),'-test.run='+pattern,'-test.parallel=8','-test.timeout=120s','-test.trace='+str(e/f'run-{i}.trace')],cwd=t/'suite',env=env|{'MODELCASE_TRACE':str(e/f'run-{i}.json')},stdout=f,stderr=f,timeout=150)
 assert q.returncode==0,i
 a=json.loads((e/f'run-{i}.json').read_text());assert sum(x['name']=='test'for x in a['spans'])==70
 sample=max((x for x in a['spans']if x['name']=='sample'),key=lambda x:x['end_ms']-x['start_ms']);result={'run':i,'elapsed_ms':a['elapsed_ms'],'max_sample':sample};results.append(result);print(result,flush=True);g.check()
(e/'runs.json').write_text(json.dumps(results,indent=2));print('ALL8_PASS',flush=True)
