import json,os,subprocess,sys,time,hashlib,statistics
from pathlib import Path
from fixture import make
root=Path(__file__).resolve().parents[2];w=Path(sys.argv[1]).resolve();temp=w/'temp';ev=w/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOCACHE=str(temp/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='')
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=root,text=True));assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
fixture=make(root,temp);(ev/'inputs.json').write_text(json.dumps({'identity':identity,'fixture':fixture,'env':{k:env[k] for k in ['GOTOOLCHAIN','GOMAXPROCS','GOGC','CGO_ENABLED']}},indent=2))
def run(args,name,en=env):
 with (ev/name).open('w') as f:r=subprocess.run(args,cwd=root,env=en,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(name)
pkg='./internal/generatedgo/code/base'
run(['go','test','-p','1','-tags=mappingspike',pkg,'-run','TestResetSpike|TestStaticPagesRangesOwnership|TestMappingFailureOwnership','-count=1','-v'],'safety.txt')
run(['go','test','-race','-p','1','-tags=mappingspike',pkg,'-run','TestResetSpikeSafety|TestResetSpikeFailures|TestResetSpikeEpochConcurrency','-count=1','-v'],'race.txt',dict(env,CGO_ENABLED='1'))
binary=temp/'cycle.test';run(['go','test','-c','-p','1','-tags=mappingspike','-o',str(binary),pkg],'build.txt')
(ev/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2))
records=[]
for phase,count in [('warmup',1),('measure',3)]:
 for rep in range(count):
  for p in [1,2]:
   for dirty in [0,1,64]:
    for arm in (['baseline','reset'] if rep%2==0 else ['reset','baseline']):
     en=dict(env,RESET_FIXTURE=str(temp),RESET_ARM=arm,RESET_P=str(p),RESET_DIRTY=str(dirty))
     utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());load=os.getloadavg()
     with (temp/'trial.txt').open('w') as f:
      pid=os.posix_spawn(str(binary),[str(binary),'-test.run=^TestResetSpikeCycle$','-test.timeout=120s'],en,file_actions=[(os.POSIX_SPAWN_DUP2,f.fileno(),1),(os.POSIX_SPAWN_DUP2,f.fileno(),2)])
     _,status,u=os.wait4(pid,0);raw=(temp/'trial.txt').read_text()
     if status: (ev/'failure.txt').write_text(raw);raise RuntimeError('cycle failed')
     rows=[json.loads(x[len('RESET_RESULT '):]) for x in raw.splitlines() if x.startswith('RESET_RESULT ')];assert len(rows)==1
     r=rows[0];r.update(phase=phase,rep=rep,utc=utc,load=load,peak_rss_bytes=u.ru_maxrss);records.append(r)
     (ev/'runs.json').write_text(json.dumps(records,indent=2));time.sleep(.15)
summary=[]
for p in [1,2]:
 for dirty in [0,1,64]:
  pairs=[]
  for rep in range(3):
   a,b=[next(r for r in records if r['phase']=='measure' and r['p']==p and r['dirty_mib']==dirty and r['rep']==rep and r['arm']==arm) for arm in ['baseline','reset']]
   pairs.append({k:100*(b[k]/a[k]-1) for k in ['wall_ms','cpu_ms','peak_rss_bytes']})
  summary.append({'p':p,'dirty_mib':dirty,'pairs_percent':pairs,'paired_medians_percent':{k:statistics.median(x[k] for x in pairs) for k in pairs[0]}})
(ev/'summary.json').write_text(json.dumps(summary,indent=2))
