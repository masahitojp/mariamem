import json,os,subprocess,sys,time,hashlib,random,platform
from pathlib import Path
root=Path(__file__).resolve().parents[2];w=Path(sys.argv[1]).resolve();temp=w/'temp';ev=w/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOCACHE=str(temp/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=root,text=True));assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
(ev/'inputs.json').write_text(json.dumps({'identity':identity,'platform':platform.platform(),'env':{k:env[k] for k in ['GOTOOLCHAIN','GOMAXPROCS','GOGC','CGO_ENABLED']}},indent=2))
binary=temp/'close.test'
with (ev/'build.txt').open('w') as log:subprocess.run(['go','test','-c','-p','1','-tags=closeeval','-o',str(binary),'.'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
(ev/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2))
def trial(cell,phase,rep,comparison,label,mode,position):
 p,cap,children=cell;en=dict(env,CLOSE_EVAL='1',CLOSE_P=str(p),CLOSE_CAP=str(cap),CLOSE_CHILDREN=str(children),CLOSE_MODE=mode)
 utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());load=os.getloadavg();start=time.perf_counter()
 with (temp/'trial.txt').open('w') as out:pid=os.posix_spawn(str(binary),[str(binary),'-test.run=^TestCloseEvaluation$','-test.timeout=120s','-test.count=1'],en,file_actions=[(os.POSIX_SPAWN_DUP2,out.fileno(),1),(os.POSIX_SPAWN_DUP2,out.fileno(),2)])
 _,status,u=os.wait4(pid,0);wall=1000*(time.perf_counter()-start);raw=(temp/'trial.txt').read_text()
 if status:(ev/'failure.txt').write_text(raw);raise RuntimeError('trial failed')
 rows=[json.loads(x[len('CLOSE_RESULT '):]) for x in raw.splitlines() if x.startswith('CLOSE_RESULT ')];assert len(rows)==1;r=rows[0];assert not r['failures'] and not r['diagnostic']
 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes']:assert r['mappings_before'][k]==r['mappings_after'][k]
 for k in ['creates','releases']:assert r['mappings_after'][k]-r['mappings_before'][k]==children
 r.update(phase=phase,rep=rep,comparison=comparison,label=label,position=position,utc=utc,load_before=load,load_after=os.getloadavg(),process_wall_ms=wall,process_cpu_ms=(u.ru_utime+u.ru_stime)*1000,peak_rss_bytes=u.ru_maxrss,minor_faults=u.ru_minflt,major_faults=u.ru_majflt,voluntary_switches=u.ru_nvcsw,involuntary_switches=u.ru_nivcsw)
 with (ev/'runs.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 time.sleep(.15)
cells=[(p,cap,n) for p,cap in [(1,1),(1,2),(2,2),(2,4)] for n in [48,480]]
for cell in cells:
 for mode in ['sync','stop']:trial(cell,'warmup',-1,'warmup','warmup',mode,0)
rnd=random.Random(119);modes={'sync-aa':('sync','sync'),'stop-aa':('stop','stop'),'ab':('sync','stop')}
for rep in range(6):
 jobs=[(cell,comp) for cell in cells for comp in modes];rnd.shuffle(jobs)
 for cell,comp in jobs:
  for pos,i in enumerate([0,1] if rep%2==0 else [1,0]):trial(cell,'measure',rep,comp,['A','B'][i],modes[comp][i],pos)
