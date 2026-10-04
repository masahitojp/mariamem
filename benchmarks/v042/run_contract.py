#!/usr/bin/env python3
"""Bounded semantic gate. An expected rejection never authorizes a soak."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
ROOT=Path(os.environ.get('V042_SOURCE_ROOT',Path(__file__).resolve().parents[2]))
REFERENCE=Path(__file__).resolve().parent/'wasm_reference.js'
CONTROL=os.environ.get('V042_RELEASE_CONTROL')=='1'
E=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE']);T=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP'])
GO='/Users/masahito/.go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin/go'
SHARED=Path('/Users/masahito/src/mysqlmem/publish/mariamem')
env=dict(os.environ,GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',CGO_ENABLED='0',GOCACHE=str(SHARED/'build/gocache'),GOMODCACHE='/Users/masahito/.go/pkg/mod')
record={'base_release':'v0.4.1','base_sha':'547fb1a6c01e5edb0daa27de273a2e94e66eb098','platform':os.uname().sysname+' '+os.uname().machine,'phases':[],'correctness_gate':'NOT_RUN','performance_started':False,'budgets':{'free_disk_gib':16,'owned_disk_gib':4,'rss_gib':4,'physical_gib':6,'phase_timeout_seconds':300}}
def save(): (E/'contract-campaign.json').write_text(json.dumps(record,indent=2)+'\n')
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(80,85))
 resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def run(name,args,expected=0,timeout=300):
 print('RUN',name,flush=True);start=time.monotonic();peak_rss=peak_physical=0
 with (E/(name+'.log')).open('wb') as log:
  chosen=dict(env,CGO_ENABLED='1') if name=='focused-runtime-race' else env
  p=subprocess.Popen(args,cwd=ROOT,env=chosen,stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits)
  try:
   while p.poll() is None:
    if time.monotonic()-start>timeout: raise RuntimeError(name+' watchdog')
    if (T/'process-cost').exists():
     rows=subprocess.check_output(['ps','-A','-o','pid=,ppid='],text=True)
     pairs=[tuple(map(int,x.split())) for x in rows.splitlines() if len(x.split())==2]
     ids={p.pid}
     for _ in range(len(pairs)):
      old=len(ids);ids.update(a for a,b in pairs if b in ids)
      if len(ids)==old:break
     cost=json.loads(subprocess.check_output([str(T/'process-cost'),*map(str,ids)],text=True))
     rss=sum(x.get('rss_bytes',0) for x in cost.values());phys=sum(x.get('primary_bytes',0) for x in cost.values())
     peak_rss=max(peak_rss,rss);peak_physical=max(peak_physical,phys)
     if rss>4*(1<<30) or phys>6*(1<<30):raise RuntimeError(name+' memory budget')
    time.sleep(.2)
  finally:
   if p.poll() is None:p.kill();p.wait()
 record['phases'].append({'name':name,'command':args,'exit_code':p.returncode,'expected_exit_code':expected,'elapsed_seconds':time.monotonic()-start,'peak_rss_bytes':peak_rss,'peak_physical_bytes':peak_physical});save()
 print('END',name,p.returncode,flush=True)
 if p.returncode!=expected: raise RuntimeError(name+' unexpected exit; retain evidence')
 return p.returncode

save()
run('build-os-counter',['cc','-O2',str(ROOT/'benchmarks/tools/process_cost.c'),'-o',str(T/'process-cost')])
run('wasm-reference',['node',str(REFERENCE)])
run('build-contract',[GO,'test','-c','-p','1','-tags=v042_release_probe' if CONTROL else '-tags=experiment_mmap','-gcflags=github.com/masahitojp/mariamem/internal/generatedgo=-d=checkptr=2','-o',str(T/'contract.test'),'./internal/generatedgo'])
record['contract_binary_sha256']=hashlib.sha256((T/'contract.test').read_bytes()).hexdigest();save()
if CONTROL:
 run('released-required-scalar-bounds',[str(T/'contract.test'),'-test.v','-test.count=1','-test.timeout=60s','-test.run=^TestV042RequiredScalarBounds$'],expected=1,timeout=80)
 record['correctness_gate']='RELEASED BASELINE ALSO FAILS: no logical scalar bounds; offset wraps'
 record['decision']='Baseline attribution only; no benchmark or runtime change';save()
else:
 run('legal-mapping-contract',[str(T/'contract.test'),'-test.v','-test.count=1','-test.timeout=60s','-test.run=TestExperimentMmap|TestV042MultipleGrow'],timeout=80)
 run('required-scalar-bounds',[str(T/'contract.test'),'-test.v','-test.count=1','-test.timeout=60s','-test.run=^TestV042RequiredScalarBounds$'],expected=1,timeout=80)
 record['correctness_gate']='BLOCKED: generated scalar OOB kills process; scalar offset arithmetic wraps';save()
 run('focused-runtime-race',[GO,'test','-race','-p','1','-count=1','./internal/generatedgo/code/base'])
 # Product checks on legal input only; these cannot override the failed memory gate.
 run('macos-product-lifecycle',[GO,'test','-p','1','-tags=integration,experiment_mmap','-v','-count=1','-timeout=240s','./tests/godefault'],timeout=260)
 record['decision']='STOP at memory semantic gate; no lifecycle expansion, no CI/platform-support claim';save()
