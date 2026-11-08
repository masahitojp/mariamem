"""Build unchanged product controls and actual accepted C guest in owned storage."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';B=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'scripts'))
from experiment_disk import DiskGuard,run_guarded
from git_identity import require_commit
from dev_guest import inventory
P=json.loads((B/'plan.json').read_text());HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip();require_commit(S,HEAD)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
for n in ['cache','modcache','gotmp','scratch']:(T/n).mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LP_','LC_'))}
env.update(GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='50',GOMEMLIMIT='3GiB',GOCACHE=str(T/'cache'),GOMODCACHE=str(T/'modcache'),GOTMPDIR=str(T/'gotmp'),TMPDIR=str(T/'scratch'))
assert subprocess.check_output(['go','version'],env=env,text=True).strip()=='go version go1.27.3 darwin/arm64'
guard=DiskGuard(W,P['min_free_gib'],P['budget_gib'])
def run(name,cmd,cwd=S,timeout=1800):
 with (E/(name+'.txt')).open('w') as log:code=run_guarded(list(map(str,cmd)),guard,cwd=cwd,env=env,output=log,timeout=timeout)
 assert code==0,(name,code)
 print(name,'PASS',flush=True)
source=T/'host-source';require_commit(S,P['host_binding_source_commit'])
subprocess.run(['git','worktree','add','--detach',str(source),P['host_binding_source_commit']],cwd=S,check=True)
# Historical host binding retains the adopted runtime bytes in the canonical tree.
assert not subprocess.check_output(['git','diff','--name-only',P['product_baseline_source_commit'],P['host_binding_source_commit'],'--','internal','python','cmd','mariamem.go','snapshot.go','go.mod','go.sum','release','guest/source.patch'],cwd=S)
run('acquire',[sys.executable,source/'benchmarks/lexerhost/acquire.py','--output',T/'acquired'])
# The dev regenerator pins its own Go1.26.10 smoke host exactly as CI did. The
# measured direct Go harnesses below both use the same local Go1.27.3.
run('regeneration',[sys.executable,source/'scripts/regenerate_release_guest.py','--development','--development-binding','lexer-prepared-c1','--guest-dir',T/'acquired/guest','--output',T/'regenerated'],timeout=3600)
dev=json.loads((T/'regenerated/development.json').read_text());accepted=json.loads((S/'benchmarks/lexerbinding/ci-42437059943/macos/development-reduced.json').read_text())
assert dev['host_source_identity']['commit']==P['host_binding_source_commit'] and dev['source_identity']['commit']==P['c_source_commit']
assert {k:v for k,v in dev['generated_inventory'].items() if k!='provenance.json'}=={k:v for k,v in accepted['generated_inventory'].items() if k!='provenance.json'}
record={'source_commit':HEAD,'plan':P,'plan_sha256':hashlib.sha256((B/'plan.json').read_bytes()).hexdigest(),'binaries':{},'installed_runtime_sha256':dev['generated_inventory'],'runtime_matches_acceptance_excluding_provenance':True,'build_failures':[]}
for arm,product in [('baseline',source),('candidate',T/'regenerated/product')]:
 mod=T/(arm+'.mod');mod.write_text((B/'go.mod').read_text().replace('=> ../..','=> '+str(product)).replace('=> ../lexercandidate','=> '+str(S/'benchmarks/lexercandidate')));mod.with_suffix('.sum').write_bytes((B/'go.sum').read_bytes())
 for obs in ['off','on']:
  overlay=[];hashes=[]
  if obs=='on':
   out=T/(arm+'-overlay');subprocess.run([sys.executable,str(S/'benchmarks/forkstages/overlay.py'),str(product),str(out)],check=True)
   overlay=['-overlay',str(out/'overlay.json')];hashes=json.loads((out/'hashes.json').read_text())
  binary=T/(arm+'-'+obs);at=time.monotonic()
  run(arm+'-'+obs+'-build',['go','build','-p','1','-trimpath','-buildvcs=true','-mod=readonly','-modfile',mod,*overlay,'-o',binary,'.'],cwd=B)
  info=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)
  assert 'vcs.revision='+HEAD in info and 'vcs.modified=false' in info
  assert '=>\t'+str(product) in info and 'CGO_ENABLED=0' in info
  record['binaries'][arm+'-'+obs]={'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'bytes':binary.stat().st_size,'build_seconds':time.monotonic()-at,'build_info':info.replace(str(W),'<WORKSPACE>'),'overlay':hashes,'guest_sha256':P[arm+'_guest_sha256']}
  (E/'inputs.json').write_text(json.dumps(record,indent=2)+'\n')
assert inventory(T/'regenerated/product/internal/generatedgo')==dev['generated_inventory']
print('BUILD COMPLETE',flush=True)
