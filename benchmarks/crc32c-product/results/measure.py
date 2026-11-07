"""Finite product-only comparison; retain every result, never retry samples."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,tarfile,shutil,statistics
w=Path(__file__).resolve().parents[1];s=w/'worktree';t=w/'temp';e=w/'evidence';base_sha='66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4'
sys.path.insert(0,str(s/'scripts'))
from git_identity import require_commit
from experiment_disk import DiskGuard,run_guarded
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()
assert head == '1057adf8fb430f5540f9d4f420f6b3f6f2012aa9'
for sha in [base_sha,head]:require_commit(s,sha)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s,text=True).strip()
assert json.loads((e/'verification.json').read_text())['steps'][-1]['name']=='lifecycle'
assert all(v['exit_code']==0 for v in json.loads((e/'verification.json').read_text())['steps'])
base=t/'baseline';base.mkdir(exist_ok=True)
with (t/'baseline.tar').open('wb') as f:subprocess.run(['git','archive',base_sha],cwd=s,stdout=f,check=True)
with tarfile.open(t/'baseline.tar') as a:a.extractall(base,filter='data')
plan={'baseline_source_commit':base_sha,'candidate_source_commit':head,'probe_sha256':hashlib.sha256((e/'probe.go').read_bytes()).hexdigest(),'parallel':[1,4],'children':48,'primary_pairs':3,'routes':['fork','fresh'],'orders':[['baseline','candidate'],['candidate','baseline'],['baseline','candidate']],'ordinary':'product only; no overlay, guest timing, static image or owner logs','processes':44,'expected_children':1572,'negative_controls':4,'criteria':'all normal state/cleanup pass, negative seed controls fail cleanly; report all pairs, no performance threshold or exclusions'}
(e/'measurement-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GO','WASMER_','WASIX_','DYLD_','LD_'))};go=Path(subprocess.check_output(['go','env','GOROOT'],env=dict(os.environ,GOTOOLCHAIN='go1.26.10'),text=True).strip())/'bin'
env.update(PATH=str(go)+os.pathsep+env['PATH'],GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0')
guard=DiskGuard(w,12,8);builds={}
for arm,source in [('baseline',base),('candidate',s)]:
 mod=t/('probe-'+arm);mod.mkdir(exist_ok=True);shutil.copyfile(e/'probe.go',mod/'main.go');shutil.copyfile(source/'go.sum',mod/'go.sum')
 (mod/'go.mod').write_text('module github.com/masahitojp/mariamem/benchmarks/crcproduct\n\ngo 1.26.0\n\nrequire (\n github.com/masahitojp/mariamem v0.0.0\n github.com/go-sql-driver/mysql v1.9.3\n filippo.io/edwards25519 v1.1.0\n)\nreplace github.com/masahitojp/mariamem => '+str(source)+'\n')
 binary=t/('probe-'+arm+'.bin');at=time.monotonic()
 with (e/('build-'+arm+'.txt')).open('w') as log:rc=run_guarded(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=false','-o',str(binary),'.'],guard,cwd=mod,env=env,output=log,timeout=1200)
 assert rc==0,arm
 builds[arm]={'library_source_commit':base_sha if arm=='baseline' else head,'probe_sha256':plan['probe_sha256'],'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'seconds':time.monotonic()-at,'build_info':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True).replace(str(w),'<WORKSPACE>')};print('BUILT',arm,flush=True)
(e/'measurement-builds.json').write_text(json.dumps(builds,indent=2)+'\n');rows=[]
def run(arm,route,p,count,kind,rep,wrong=False):
 guard.check()
 name=f'{kind}-{route}-p{p}-{rep}-{arm}';out=e/(name+'.json');err=e/(name+'.stderr.txt');args=[str(t/('probe-'+arm+'.bin')),'-route',route,'-parallel',str(p),'-count',str(count)]
 if wrong:args+=['-expected-sum','31']
 # Capture both streams without pipe buffers blocking the guest.
 with out.open('wb') as f,err.open('wb') as log:
  proc=subprocess.Popen(args,cwd=s,env=env,stdout=f,stderr=log);start=time.monotonic();next_check=start+10
  while proc.poll() is None:
   try:
    if time.monotonic()>=next_check:
     guard.check();next_check=time.monotonic()+10
   except BaseException:proc.kill();proc.wait();raise
   if time.monotonic()-start>120:proc.kill();proc.wait();raise TimeoutError(name)
   time.sleep(.1)
  rc=proc.returncode
 data=json.loads(out.read_text());assert data['Route']==route and data['Parallel']==p and data['Count']==count
 assert all(data['Cleanup'][k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures','grow_failures'])
 if wrong:assert rc==1 and not data['Success'] and 'pristine oracle' in data['error']
 else:assert rc==0 and data['Success'] and all(not v.get('error') for v in data['Samples'])
 rows.append({'name':name,'arm':arm,'route':route,'parallel':p,'kind':kind,'rep':rep,'exit_code':rc,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'data':data});(e/'measurement-records.json').write_text(json.dumps(rows,indent=2)+'\n');print(name,'PASS' if not wrong else 'EXPECTED FAIL',flush=True)
for arm in ['baseline','candidate']:
 for route in ['fork','fresh']:
  for p in [1,4]:run(arm,route,p,4,'pilot',0)
  run(arm,route,1,1,'negative',0,True)
for p in [1,4]:
 for route in ['fork','fresh']:
  for arm in ['baseline','candidate']:run(arm,route,p,48,'warmup',0)
  for rep,arms in enumerate(plan['orders']):
   for arm in arms:run(arm,route,p,48,'primary',rep)
assert len(rows)==44 and sum(v['data']['Count'] for v in rows)==1572
summary=[]
for p in [1,4]:
 for route in ['fork','fresh']:
  pairs=[]
  for rep in range(3):
   get=lambda arm:next(v['data'] for v in rows if v['kind']=='primary' and v['arm']==arm and v['route']==route and v['parallel']==p and v['rep']==rep)
   a,b=get('baseline'),get('candidate');metric=lambda d:{**{k:d[k] for k in ['Batch','BatchCPU','Suite','SuiteCPU']},**{k+'P50':statistics.median(v[k] for v in d['Samples']) for k in ['Startup','Cleanup','SQL','Seed']}}
   av,bv=metric(a),metric(b);pairs.append({'rep':rep,'baseline':av,'candidate':bv,'difference':{k:bv[k]-av[k] for k in av}})
  summary.append({'parallel':p,'route':route,'pairs':pairs,'median_paired_difference':{k:statistics.median(v['difference'][k] for v in pairs) for k in pairs[0]['difference']}})
(e/'measurement-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('COMPLETE',flush=True)
