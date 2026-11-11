from pathlib import Path
import subprocess,os,json,hashlib,tarfile,time
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
refs={'baseline':'584004b21132e28886330484bfec00fdda99642c','candidate':'1f0e6fc4313278c10027864285df7b70a85f91e4'}
harness='d24087eedd21c6384c231fb119c8e98da7b370aa'
def run(cmd,**kw):return subprocess.check_output(cmd,cwd=S,text=True,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def inventory(p):return {str(f.relative_to(p)):sha(f.read_bytes()) for f in sorted(p.rglob('*')) if f.is_file()}
assert not run(['git','status','--porcelain'])
identities={}
for key,ref in {**refs,'harness':harness}.items():
 x=json.loads(run(['python3','scripts/git_identity.py','inspect',ref]));assert x['object_type']=='commit' and x['source_commit']==ref;identities[key]=x
# Freeze the question, sample size and budget before compilation or measurement.
dump(E/'plan.json',{'question':'Does the assembled timer candidate improve startup and complete Go Pipe shop70 execution relative to current main?','sources':identities,'scope':'Both SQL clock correction and bounded probe omission vs unmodified main, not isolation of the probe alone. Single local Mac; no pgmem/new Ubuntu performance.','workload':'Existing immutable timer_calibration runner; 16MiB buffer pool/read1; GOMAXPROCS8 GOGC100; no internal observers. 50 shared-child reads +20 private-child writes, cap=P+1, P4/P8.','sampling':{'lifecycle_pairs':6,'fresh_per_batch':8,'fork_per_batch':16,'shop_pairs_per_parallelism':5,'warmup_processes':6,'order':'alternating arms and P4/P8 order','tail_policy':'retain every sample, no outcome-selected repeats'},'exit':'Report paired wall/CPU changes, lifecycle and child-stage distributions, >100ms tails, correctness and cleanup; inconclusive effects remain inconclusive. No speed threshold silently converted to approval.','budget':{'active_hours':2,'tooling_minutes':30,'heavy_CI_submissions':0,'disk_gib':8,'min_free_gib':8},'measurement_clock':'host monotonic wall and process rusage CPU, not corrected guest SQL timer','baseline_negative_control':'Baseline ANALYZE may report zero (known defect); require valid SQL rows, subsequent SELECT and cleanup. Candidate delayed report must be [18, client wall+5]ms.'})
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','GIT_'))}
env.update(GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2')
for arm,ref in refs.items():
 A=T/arm;A.mkdir();archive=T/(arm+'.tar')
 with archive.open('wb') as f:subprocess.run(['git','archive',ref],cwd=S,stdout=f,check=True)
 with tarfile.open(archive) as tf:tf.extractall(A,filter='data')
 archive.unlink()
 before=inventory(A/'internal/generatedgo')
 ha=T/'harness.tar'
 with ha.open('wb') as f:subprocess.run(['git','archive',harness,'tests/timer_calibration/runner'],cwd=S,stdout=f,check=True)
 with tarfile.open(ha) as tf:tf.extractall(A,filter='data')
 ha.unlink();runner=A/'tests/timer_calibration/runner'
 binary=T/(arm+'.test');started=time.monotonic()
 print(arm,'compile start',flush=True)
 with (T/(arm+'-build.log')).open('w') as f:
  r=subprocess.run(['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-c','-o',str(binary),'./maria/store'],cwd=runner,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
 if r.returncode:print((T/(arm+'-build.log')).read_text()[-5000:]);raise SystemExit(r.returncode)
 assert before==inventory(A/'internal/generatedgo')
 buildinfo=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True).replace(str(T),'<TEMP>')
 x={'source':identities[arm],'harness_source':identities['harness'],'harness_files_sha256':inventory(runner),'generated_inventory_sha256':sha(json.dumps(before,sort_keys=True).encode()),'guest_sha256':json.loads((A/'release/generated-go-build.json').read_text()).get('guest_sha256'),'binary_sha256':sha(binary.read_bytes()),'buildinfo':buildinfo,'compile_wall_seconds':time.monotonic()-started,'buildvcs':False,'source_attribution':'Exact commit archive via git_identity.py; harness injected identically; product generated inventory unchanged by build.'}
 dump(E/(arm+'-runner.json'),x);print(arm,'compile PASS',round(x['compile_wall_seconds'],1),flush=True)
a=json.loads((E/'baseline-runner.json').read_text());b=json.loads((E/'candidate-runner.json').read_text());assert a['harness_files_sha256']==b['harness_files_sha256']
print('identical harness PASS',flush=True)
