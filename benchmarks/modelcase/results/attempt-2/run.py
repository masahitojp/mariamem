"""Pinned three-model application-suite comparison; pilot gates the matrix."""
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['pilot','matrix'],required=True);a=p.parse_args()
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence'
sys.path.insert(0,str(C/'scripts'))
from git_identity import require_commit,inspect_ref,verify_release_pin,ReleasePin
T.mkdir(exist_ok=True)
def save(name,d):
 q=E/name;q.parent.mkdir(exist_ok=True,parents=True);q.write_text(json.dumps(d,indent=2)+'\n')
def command(cmd,cwd=C,env=None,log='command.txt',timeout=600):
 print('RUN',log,flush=True)
 with (E/log).open('w') as f:return subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
identity=inspect_ref(C,'v0.6.0');verify_release_pin(C,ReleasePin('v0.6.0',identity.object_sha,identity.source_commit))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip();require_commit(C,commit)
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C,text=True)
prod=T/'product'
if not prod.exists():
 assert command(['git','clone','--shared','--no-checkout',C,prod],log='clone.txt')==0
 assert command(['git','checkout','--detach',identity.source_commit],cwd=prod,log='checkout.txt')==0
require_commit(prod,identity.source_commit);assert not subprocess.check_output(['git','status','--porcelain'],cwd=prod,text=True)
module=T/'runner';module.mkdir(exist_ok=True)
for f in (C/'benchmarks/modelcase').iterdir():
 if f.suffix in ['.go','.mod','.sum']:shutil.copyfile(f,module/f.name)
go=Path(subprocess.check_output(['go','env','GOROOT'],env=dict(os.environ,GOTOOLCHAIN='go1.26.10'),text=True).strip())/'bin/go'
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_'))}
env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'),GOMAXPROCS='8',PATH=str(go.parent)+os.pathsep+os.environ['PATH'])
for n in ['go-cache','go-mod','go-tmp','scratch']:(T/n).mkdir(exist_ok=True)
env['DOCKER_HOST']=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip();env['TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE']='/var/run/docker.sock'
image='mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
env['MODELCASE_IMAGE']=image
assert command([go,'mod','edit','-replace=github.com/masahitojp/mariamem='+str(prod)],cwd=module,env=env,log='replace.txt')==0
binary=T/'modelcase.test'
if a.phase=='pilot':
 assert command([go,'test','-c','-mod=readonly','-p','1','-vet=off','-trimpath','-o',binary,'.'],cwd=module,env=env,log='build.txt')==0
 info=dict(product_source_commit=identity.source_commit,tag_object_sha=identity.object_sha,harness_source_commit=commit,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),go=subprocess.check_output([go,'version'],env=env,text=True).strip(),build_info=subprocess.check_output([go,'version','-m',binary],env=env,text=True),harness_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (C/'benchmarks/modelcase').iterdir() if f.is_file()},docker=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True)),image=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True))[0],ryuk_image=json.loads(subprocess.check_output(['docker','image','inspect','testcontainers/ryuk:0.13.0'],text=True))[0],host=dict(macos=platform.mac_ver()[0],machine=platform.machine()),go_compile_timed=False,image_pull_timed=False)
 # Drop host-specific paths/config/secrets from Docker metadata; retain capacity/version.
 info['docker']={k:info['docker'].get(k) for k in ['ServerVersion','OperatingSystem','OSType','Architecture','NCPU','MemTotal','Driver','ContainersRunning']}
 for key in ['image','ryuk_image']:
  info[key]={k:info[key].get(k) for k in ['Id','RepoTags','RepoDigests','Architecture','Os']}
 save('inputs.json',info)
else:
 info=json.loads((E/'inputs.json').read_text());assert info['binary_sha256']==hashlib.sha256(binary.read_bytes()).hexdigest()
 assert json.loads((E/'pilot-result.json').read_text())['result']=='PASS'
records=[]
def one(mode,parallel,rep,warmup=False,negative=False):
 label=f'{"negative" if negative else "warmup" if warmup else "trial"}-{mode}-p{parallel}-{rep}';folder=E/('pilot' if a.phase=='pilot' else 'matrix');folder.mkdir(exist_ok=True)
 out=folder/(label+'.json');log=folder/(label+'.txt');scratch=T/'scratch'/label;scratch.mkdir(exist_ok=True)
 ce=dict(env,MODELCASE_MODE=mode,MODELCASE_OUTPUT=str(out),TMPDIR=str(scratch))
 if negative:ce['MODELCASE_CORRUPT_SEED']='1'
 cmd=[binary,'-test.run','^TestModelcase$/read-0-01$' if negative else '^TestModelcase$','-test.parallel',parallel,'-test.timeout','240s','-test.v']
 begin=time.monotonic();code=command(cmd,cwd=module,env=ce,log=str(log.relative_to(E)),timeout=255);wall=time.monotonic()-begin
 assert out.exists(),f'{label} failed before report';data=json.loads(out.read_text())
 # Inspect only DB IDs owned by this exact test process. Never stop other containers.
 absent=[]
 for cid in data['container_ids']:
  check=subprocess.run(['docker','inspect',cid],capture_output=True,text=True);assert check.returncode!=0 and ('No such' in check.stderr or 'not found' in check.stderr),cid;absent.append(cid)
 residue=list(scratch.iterdir())
 row=dict(label=label,mode=mode,parallelism=parallel,repetition=rep,warmup=warmup,negative_control=negative,returncode=code,wall_ms=wall*1000,suite_ms=data['suite_ms'],cases=len(data['cases']),containers_absent=absent,scratch_empty=not residue,report=out.relative_to(E).as_posix())
 records.append(row);save('pilot-records.json' if a.phase=='pilot' else 'records.json',records)
 assert not residue,f'owned scratch survived {label}'
 if negative:
  assert code!=0 and not data['completed'] and 'pristine input differs' in log.read_text() and data['cleanup_complete'],label
 else:
  assert code==0 and data['completed'] and data['cleanup_complete'] and len(data['cases'])==70,label
  assert all(data['cases'].values()),label
 print('PASS',label,round(wall*1000,1),'ms',flush=True)
if a.phase=='pilot':
 for mode in ['mariamem','shared','workers']:one(mode,1,0)
 one('mariamem',1,0,negative=True)
 save('pilot-result.json',dict(result='PASS',cells=3,negative_seed_oracle='FAIL_EXPECTED_AND_CLEANED'))
else:
 modes=['mariamem','shared','workers']
 for parallel in [1,2,4,8]:
  for mode in modes:one(mode,parallel,-1,warmup=True)
  for rep in range(5):
   start=(rep+parallel)%3
   for mode in modes[start:]+modes[:start]:one(mode,parallel,rep)
 save('completion.json',dict(result='PASS',measured_suites=60,warmup_suites=12,measured_cases=4200,environment='one local macOS host; native arm64 Linux Docker VM',scope='No performance pass threshold'))
