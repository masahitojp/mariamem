import importlib.util,json,os,subprocess,sys,time,hashlib,random
from pathlib import Path
root=Path(__file__).resolve().parents[2];w=Path(sys.argv[1]).resolve();temp=w/'temp';ev=w/'evidence'
s=importlib.util.spec_from_file_location('fixture',root/'benchmarks/mapping-reset/fixture.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOCACHE=str(temp/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='')
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=root,text=True));assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
fixture=f.make(root,temp);(ev/'inputs.json').write_text(json.dumps({'identity':identity,'fixture':fixture,'env':{k:env[k] for k in ['GOTOOLCHAIN','GOMAXPROCS','GOGC','CGO_ENABLED']}},indent=2))
binary=temp/'aa.test'
with (ev/'build.txt').open('w') as log:subprocess.run(['go','test','-c','-p','1','-tags=mappingspike','-o',str(binary),'./internal/generatedgo/code/base'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
(ev/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)},indent=2))
records=[]
def trial(cell,phase,rep,label,position):
 p,dirty,cycles=cell;en=dict(env,RESET_FIXTURE=str(temp),RESET_ARM='baseline',RESET_P=str(p),RESET_DIRTY=str(dirty),AA_CYCLES=str(cycles))
 utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());load=os.getloadavg();start=time.perf_counter()
 with (temp/'trial.txt').open('w') as out:pid=os.posix_spawn(str(binary),[str(binary),'-test.run=^TestResetSpikeCycle$','-test.timeout=120s'],en,file_actions=[(os.POSIX_SPAWN_DUP2,out.fileno(),1),(os.POSIX_SPAWN_DUP2,out.fileno(),2)])
 _,status,u=os.wait4(pid,0);wall=1000*(time.perf_counter()-start);raw=(temp/'trial.txt').read_text()
 if status:(ev/'failure.txt').write_text(raw);raise RuntimeError('trial failed')
 rows=[json.loads(x[len('RESET_RESULT '):]) for x in raw.splitlines() if x.startswith('RESET_RESULT ')];assert len(rows)==1;r=rows[0]
 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes']:assert r['before'][k]==r['after'][k]
 assert r['after']['creates']-r['before']['creates']==p*cycles
 assert r['after']['releases']-r['before']['releases']==p*cycles
 r.update(phase=phase,rep=rep,label=label,position=position,utc=utc,load_before=load,load_after=os.getloadavg(),process_wall_ms=wall,process_cpu_ms=(u.ru_utime+u.ru_stime)*1000,peak_rss_bytes=u.ru_maxrss,minor_faults=u.ru_minflt,major_faults=u.ru_majflt,voluntary_switches=u.ru_nvcsw,involuntary_switches=u.ru_nivcsw)
 records.append(r);(ev/'runs.json').write_text(json.dumps(records,indent=2));time.sleep(.15)
cells=[(p,d,c) for p in [1,2] for d in [0,1,64] for c in [48,480]]
for cell in cells:trial(cell,'warmup',-1,'warmup',0)
rnd=random.Random(119)
for rep in range(6):
 order=list(cells);rnd.shuffle(order)
 for cell in order:
  for pos,label in enumerate(['A','Aprime'] if rep%2==0 else ['Aprime','A']):trial(cell,'measure',rep,label,pos)
