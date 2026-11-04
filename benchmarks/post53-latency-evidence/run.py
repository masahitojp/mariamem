"""Light same-harness v0.6.0/current-main check, not a performance gate."""
import hashlib,json,os,platform,statistics,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';C=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(C/'scripts'))
from git_identity import inspect_ref,require_commit,verify_release_pin,ReleasePin,verify_go_binary
start=time.monotonic()
def save(n,v):
 p=E/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def run(args,cwd=C,env=None,log='command.txt',timeout=600):
 print('RUN',log,flush=True)
 with (E/log).open('w') as f:subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=inspect_ref(C,'v0.6.0');verify_release_pin(C,ReleasePin('v0.6.0',base.object_sha,base.source_commit));current=inspect_ref(C,'6e29c1cd125aa95f564969b905cbff462d4f0e74')
refs={'baseline':base.source_commit,'candidate':current.source_commit}
save('release-pin.json',dict(version=1,release_tag='v0.6.0',tag_object_sha=base.object_sha,source_commit=base.source_commit))
goenv=dict(os.environ,GOTOOLCHAIN='go1.26.10');go=Path(subprocess.check_output(['go','env','GOROOT'],env=goenv,text=True).strip())/'bin/go'
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_'))};env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',PATH=str(go.parent)+os.pathsep+os.environ['PATH'])
(T/'bin').mkdir(exist_ok=True);(T/'scratch').mkdir(exist_ok=True);env['TMPDIR']=str(T/'scratch');env['GOTMPDIR']=str(T/'scratch')
roots={label:T/label for label in refs}
identity={'sources':refs,'baseline_tag_object_sha':base.object_sha,'platform':platform.platform(),'machine':platform.machine(),'toolchain':'go1.26.10','cgo_enabled':'0','flags':['-p','1','-trimpath','-buildvcs=true'],'harness':{},'binaries':{},'pairs':3,'warmup_pairs':1,'instances_per_suite':4,'scope':'local Go ordinary latency; no Python/resource/cold/cross-platform campaign','script_sha256':digest(Path(__file__)),'environment':{k:env.get(k) for k in ['GOMAXPROCS','GOMEMLIMIT','GOGC']}}
for key in ['hw.memsize','hw.logicalcpu','machdep.cpu.brand_string']:
 identity[key]=subprocess.check_output(['sysctl','-n',key],text=True).strip()
for label,root in roots.items():
 run(['git','clone','--shared','--no-checkout',C,root],log='clone-'+label+'.txt');run(['git','checkout','--detach',refs[label]],cwd=root,log='checkout-'+label+'.txt');require_commit(root,refs[label]);assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
 for name in ['main.go','resources.go']:
  h=digest(root/'benchmarks/ownedprepared'/name);identity['harness'].setdefault(name,h);assert identity['harness'][name]==h
 identity.setdefault('guest_sha256',{})[label]=json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
 binary=T/'bin'/label
 run([go,'build','-p','1','-trimpath','-buildvcs=true','-o',binary,'./benchmarks/ownedprepared'],cwd=root,env=env,log='build-'+label+'.txt')
 info=verify_go_binary(root,binary,refs[label],go=go);identity['binaries'][label]={'sha256':digest(binary),'build_info':info.replace(str(T),'<temp>')};save('inputs.json',identity)
cases=[('light',0,1,1),('fixture',10,8,1),('parallel',10,8,4)];records=[]
for rep in range(-1,3):
 for case,size,tables,workers in cases:
  for mode in ['fresh','fork']:
   order=['baseline','candidate'] if (rep+(mode=='fork'))%2==0 else ['candidate','baseline']
   for label in order:
    name=f'{case}-{mode}-{rep}-{label}';out=T/(name+'.json')
    run([T/'bin'/label,'-payload-mib',size,'-tables',tables,'-workers',workers,'-forks',4,'-workload','app-connections','-lifecycle',mode,'-label',refs[label],'-out',out],cwd=roots[label],env=env,log='last-trial.txt',timeout=90)
    data=json.loads(out.read_text())
    records.append(dict(label=label,case=case,mode=mode,repetition=rep,seconds=data['suite_product_seconds'],cpu_seconds=data['suite_cpu_seconds'],operations=data['operations'],fds_before=data['fds_before'],fds_after=data['fds_after']))
    save('records.json',records);out.unlink()
summary={}
for case,*_ in cases:
 for mode in ['fresh','fork']:
  d={label:[r['seconds'] for r in records if r['case']==case and r['mode']==mode and r['label']==label and r['repetition']>=0] for label in refs};med={k:statistics.median(v) for k,v in d.items()}
  summary[case+'-'+mode]={'raw_seconds':d,'median_seconds':med,'change_percent':100*(med['candidate']/med['baseline']-1),'slower_pairs':sum(c>b for b,c in zip(d['baseline'],d['candidate'])),'min_max_seconds':{k:[min(v),max(v)] for k,v in d.items()}}
save('summary.json',summary);save('completion.json',{'result':'PASS','executions':len(records),'elapsed_seconds':time.monotonic()-start,'scratch_empty':not any((T/'scratch').iterdir())});print(json.dumps(summary,indent=2),flush=True)
