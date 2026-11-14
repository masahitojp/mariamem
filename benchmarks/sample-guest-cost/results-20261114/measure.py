from pathlib import Path
import subprocess,os,json,hashlib,time
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1')
records=[]
def run(engine,name,args,extra={}):
 at=time.monotonic();binary=T/(engine+'-suite')/'probe'
 with (E/(name+'.txt')).open('w')as f:
  p=subprocess.run([str(binary)]+args,cwd=T/(engine+'-suite'),env=dict(env,**extra),stdout=f,stderr=f,timeout=180)
 records.append(dict(engine=engine,name=name,code=p.returncode,seconds=time.monotonic()-at,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),args=args,env=extra))
 (E/'records.json').write_text(json.dumps(records,indent=2))
 if p.returncode:raise RuntimeError(name)
for engine in ['maria','pg']:
 run(engine,engine+'-plans',['-test.run=^TestRevenuePlans$','-test.v'])
for i in range(3):
 for engine in (['maria','pg'] if i%2==0 else ['pg','maria']):run(engine,f'{engine}-query-{i}',['-test.run=^TestRevenueProbe$','-test.v'])
run('maria','sample-profile',['-test.run=^TestSampleProfile$','-test.v'],{'SAMPLE_PROFILE':'1','PROFILE_DIR':str(E)})
for p in [1,8]:
 for i in range(3):
  for engine in ['maria','pg']:
   for arm in ([0,1] if i%2==0 else [1,0]):
    name=f'{engine}-p{p}-r{i}-a{arm}'
    run(engine,name,['-test.run=^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$',f'-test.parallel={p}'],{'REVENUE_PREAGG':str(arm),'MODELCASE_TRACE':str(E/(name+'.json'))})
print('DONE',flush=True)
