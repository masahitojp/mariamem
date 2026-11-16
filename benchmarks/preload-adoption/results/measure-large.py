import json,os,subprocess,sys,time,hashlib,random,re
from pathlib import Path
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence';d=e/'large';d.mkdir(exist_ok=True)
sys.path.insert(0,str(r/'scripts'));from experiment_disk import DiskGuard
g=DiskGuard(w,8,6);g.check();identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert identity==json.loads((e/'inputs.json').read_text())['identity'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=r);assert hashlib.sha256((t/'large').read_bytes()).hexdigest()==(e/'large-sha256.txt').read_text()
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',GODEBUG='');deadline=time.monotonic()+900;records=[]
def power():
 q=subprocess.run(['pmset','-g','batt'],text=True,capture_output=True);return q.stdout+q.stderr
def trial(n,p,pair,arm):
 g.check();assert time.monotonic()<deadline;name=f'n{n}-p{p}-pair{pair}-{arm}';before=power();load=os.getloadavg();start=time.monotonic()
 with (d/(name+'.txt')).open('w')as f:q=subprocess.run(['/usr/bin/time','-l',str(t/'large'),f'-rows={n}',f'-p={p}','-out='+str(d/(name+'.json'))],env=env|{'EXPERIMENT_BUFFER_LOAD':arm},stdout=f,stderr=f,timeout=min(180,max(1,deadline-time.monotonic())))
 wall=(time.monotonic()-start)*1000;after=power();row={'name':name,'n':n,'p':p,'pair':pair,'arm':arm,'returncode':q.returncode,'wall_ms':wall,'power_before':before,'power_after':after,'load_before':load,'load_after':os.getloadavg()};records.append(row);(e/'large-records.json').write_text(json.dumps(records,indent=2));assert q.returncode==0,name
 j=json.loads((d/(name+'.json')).read_text());assert j['success']and len(j['samples'])==8 and j['mapping_stats']['active_mappings']==0
 row.update(j);row['rss_bytes']=int(re.search(r'(\d+)\s+maximum resident set size',(d/(name+'.txt')).read_text())[1]);(e/'large-records.json').write_text(json.dumps(records,indent=2));print(name,round(j['elapsed_ms'],2),round(j['batch_ms'],2),flush=True);g.check()
cells=[(4096,1),(4096,8),(24576,1),(24576,8)]
for n,p in cells:
 for arm in ['ON','OFF']:trial(n,p,-1,arm)
rng=random.Random(217)
for pair in range(5):
 order=cells.copy();rng.shuffle(order)
 for n,p in order:
  for arm in (['ON','OFF']if pair%2==0 else ['OFF','ON']):trial(n,p,pair,arm)
assert len(records)==48
print('ALL48PROCESSES_PASS',flush=True)
