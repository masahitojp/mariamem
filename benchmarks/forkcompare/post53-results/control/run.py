"""Same-session v0.6.0/current A/B control after prior-cohort CPU change."""
from pathlib import Path
import os,sys,json,time,subprocess,hashlib,ctypes,importlib.util
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';P=W.parent/'post53-pgmem';C=P/'temp/harness';B=C/'benchmarks/forkcompare'
sys.path.insert(0,str(C/'scripts'))
from git_identity import inspect_ref,ReleasePin,verify_release_pin,verify_go_binary
from experiment_disk import stop_group
spec=importlib.util.spec_from_file_location('prior_runner',P/'evidence/run.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))};env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOTMPDIR=str(T/'scratch'),TMPDIR=str(T/'scratch'));(T/'scratch').mkdir();(T/'bin').mkdir()
def run(cmd,cwd=C,log='build.txt'):
 print('RUN',log,flush=True)
 with (E/log).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
base=T/'baseline';run(['git','clone','--shared','--no-checkout',C,base],log='clone.txt');run(['git','checkout','--detach','b3b3b46a8807482ad3f96725af86e031fe369b01'],cwd=base,log='checkout.txt');pin=ReleasePin('v0.6.0','b57183b08d48884840111e8b53daa500734337f0','b3b3b46a8807482ad3f96725af86e031fe369b01');verify_release_pin(base,pin);assert not subprocess.check_output(['git','status','--porcelain'],cwd=base)
mod=T/'control.mod';mod.write_bytes((B/'go.mod').read_bytes());mod.with_suffix('.sum').write_bytes((B/'go.sum').read_bytes());run(['go','mod','edit','-modfile',mod,'-replace=github.com/masahitojp/mariamem='+str(base)],cwd=B,log='modfile.txt')
binary=T/'bin/baseline';run(['go','build','-p','1','-mod=readonly','-modfile',mod,'-trimpath','-buildvcs=true','-o',binary,'./maria'],cwd=B)
harness=inspect_ref(C,'HEAD').source_commit;info=verify_go_binary(C,binary,harness,toolchain='go1.27.3');binaries={'baseline':binary,'main':P/'temp/temp/bin/mariamem'}
inputs={'question':'Does the historical CPU increase persist against same-session v0.6.0 on the unchanged harness?','sources':{'baseline':pin.source_commit,'main':'6e29c1cd125aa95f564969b905cbff462d4f0e74'},'tag_object_sha':pin.tag_object_sha,'harness_source_commit':harness,'binary_hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in binaries.items()},'baseline_build_info':info.replace(str(W),'<control>').replace(str(P),'<comparison>'),'module_file_delta':'Only alternate modfile replaces the mariamem dependency with a verified clean v0.6.0 checkout. Product/harness files unchanged.','go':'go1.27.3','gomaxprocs':8,'route':'tcp','count':48,'repeats':3,'warmup':1};(E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
records=[]
for rep in [-1,0,1,2]:
 cells=[('baseline',4),('main',4),('baseline',8),('main',8)]
 if rep%2:cells=list(reversed(cells))
 for label,p in cells:
  name=f'{label}-p{p}-r{rep}';sync=T/name;sync.mkdir();scratch=T/'scratch'/name;scratch.mkdir();out=E/(name+'.json');samples=[]
  with (E/'last-trial.txt').open('w') as log:
   proc=subprocess.Popen([str(binaries[label]),'-route','tcp','-parallel',str(p),'-count','48','-out',str(out),'-sync-dir',str(sync)],cwd=B,env=dict(env,TMPDIR=str(scratch)),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:
    deadline=time.monotonic()+100
    while not (sync/'ready').exists():assert proc.poll() is None and time.monotonic()<deadline;time.sleep(.02)
    baseline=prior.rss(proc.pid);start=time.monotonic();(sync/'go').write_text('go')
    while not (sync/'done').exists():
     assert proc.poll() is None and time.monotonic()<deadline;samples.append({'offset_ms':1000*(time.monotonic()-start),'rss_bytes':prior.rss(proc.pid)});time.sleep(.02)
    assert proc.wait(timeout=30)==0
   finally:stop_group(proc)
  d=json.loads(out.read_text());assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and len(d['samples'])==48 and all(s['oracle'] and s['cleanup_complete'] and not s.get('error') for s in d['samples']);assert not any(scratch.iterdir())
  records.append({'backend':label,'parallel':p,'repetition':rep,'warmup':rep<0,'wall_ms':d['batch_ms'],'cpu_ms':d['cpu_user_ms']+d['cpu_system_ms'],'baseline_rss_bytes':baseline,'peak_rss_bytes':max(x['rss_bytes'] for x in samples),'report':name+'.json'})
  (E/'records.json').write_text(json.dumps(records,indent=2)+'\n');print('PASS',name,round(d['batch_ms'],1),flush=True)
(E/'completion.json').write_text(json.dumps({'result':'PASS','ordinary':12,'warmup':4,'children_per_process':48},indent=2)+'\n')
