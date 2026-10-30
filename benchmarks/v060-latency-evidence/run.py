"""Bounded same-toolchain release latency comparison; no runtime changes."""
import hashlib,json,os,platform,statistics,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1]; E=W/'evidence'; T=W/'temp'; C=W/'worktree'
sys.path.insert(0,str(C/'scripts'))
from git_identity import inspect_ref,require_commit,verify_release_pin,ReleasePin,verify_go_binary
started=time.monotonic()
def save(name,data):
 p=E/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')
def run(argv,cwd=C,env=None,log=None,timeout=600):
 print('RUN',log or argv[0],flush=True)
 with (E/(log or 'command.txt')).open('w') as f:
  subprocess.run(list(map(str,argv)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
refs={k:inspect_ref(C,v) for k,v in [('baseline','v0.5.3'),('candidate','v0.6.0')]}
for name,tag in [('baseline','v0.5.3'),('candidate','v0.6.0')]:
 i=refs[name]; pin=ReleasePin(tag,i.object_sha,i.source_commit);verify_release_pin(C,pin)
 save('release-'+tag+'.json',dict(version=1,release_tag=tag,tag_object_sha=i.object_sha,source_commit=i.source_commit))
roots={'baseline':T/'baseline','candidate':T/'candidate'}
for label,root in roots.items():
 if not root.exists():
  run(['git','clone','--shared','--no-checkout',C,root],log='clone-'+label+'.txt')
  run(['git','checkout','--detach',refs[label].source_commit],cwd=root,log='checkout-'+label+'.txt')
for label,root in roots.items():require_commit(root,refs[label].source_commit);assert subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)==''
baseenv=dict(os.environ,GOTOOLCHAIN='go1.26.10')
go=Path(subprocess.check_output(['go','env','GOROOT'],env=baseenv,text=True).strip())/'bin/go'
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_'))}
env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'),PATH=str(go.parent)+os.pathsep+os.environ['PATH'])
for p in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/p).mkdir(exist_ok=True)
identity=dict(sources={k:v.source_commit for k,v in refs.items()},go=subprocess.check_output([go,'version'],env=env,text=True).strip(),python=sys.version,host=dict(macos=platform.mac_ver()[0],architecture=platform.machine()),flags=['-p','1','-trimpath','-buildvcs=true'],binaries={},harness={},scope='Local macOS latency; common APIs only; no 100MiB/qualification/CI',plain_pairs=6,python_resource_pairs=1,heavy_ci_submissions=0,active_work_budget_minutes=120,tooling_budget_minutes=30,execution_timeout_seconds=1800)
for n in ['benchmarks/ownedprepared/main.go','benchmarks/ownedprepared/resources.go','benchmarks/sharedhost/campaign.py','benchmarks/sharedhost/workflow.py']:
 assert (roots['baseline']/n).read_bytes()==(C/n).read_bytes(),n
 identity['harness'][n]=digest(C/n)
save('inputs.json',identity)
for label,root in roots.items():
 for kind,target in [('host','./cmd/mariamem-host'),('go','./benchmarks/ownedprepared')]:
  binary=T/'bin'/(label+'-'+kind)
  if not binary.exists():
   run([go,'build','-p','1','-trimpath','-buildvcs=true','-o',binary,target],cwd=root,env=env,log='build-'+label+'-'+kind+'.txt')
  info=verify_go_binary(root,binary,refs[label].source_commit,go=go)
  identity['binaries'][label+'-'+kind]=dict(sha256=digest(binary),build_info=info)
  save('inputs.json',identity)
cases=[('light',0,1,1),('fixture',10,8,1),('parallel',10,8,4)]
records=[]
for rep in range(-1,6):
 for case,size,tables,workers in cases:
  for mode in ['fresh','fork']:
   order=['baseline','candidate'] if (rep+(mode=='fork'))%2==0 else ['candidate','baseline']
   for label in order:
    name=f'go/{"warmup" if rep<0 else "plain"}-{case}-{mode}-{rep}-{label}'
    out=E/(name+'.json');out.parent.mkdir(exist_ok=True)
    run([T/'bin'/(label+'-go'),'-payload-mib',size,'-tables',tables,'-workers',workers,'-forks',4,'-workload','app-connections','-lifecycle',mode,'-label',refs[label].source_commit,'-out',out],cwd=roots[label],env=env,log=name+'.txt',timeout=180)
    data=json.loads(out.read_text())
    records.append(dict(name=name,label=label,case=case,mode=mode,repetition=rep,seconds=data['suite_product_seconds']))
    save('go-records.json',records)
run([sys.executable,C/'benchmarks/sharedhost/campaign.py','--baseline',roots['baseline'],'--baseline-commit',refs['baseline'].source_commit,'--baseline-host',T/'bin/baseline-host','--candidate',roots['candidate'],'--candidate-commit',refs['candidate'].source_commit,'--candidate-host',T/'bin/candidate-host','--output',E/'python','--scratch',T/'scratch','--scales','small','medium','--plain-repeats',6,'--resource-repeats',1],env=env,log='python-campaign.txt',timeout=600)
summary={}
for case,*_ in cases:
 for mode in ['fresh','fork']:
  d={label:[r['seconds'] for r in records if r['case']==case and r['mode']==mode and r['label']==label and r['repetition']>=0] for label in roots}
  med={label:statistics.median(v) for label,v in d.items()}
  summary[case+'-'+mode]=dict(raw_seconds=d,median_seconds=med,change_percent=100*(med['candidate']/med['baseline']-1))
save('go-summary.json',summary)
save('completion.json',dict(result='PASS',go_executions=len(records),python_executions=28,elapsed_seconds=time.monotonic()-started,scratch_empty=not any((T/'scratch').iterdir())))
print('COMPLETE',json.dumps(summary),flush=True)
