"""Copy to owned evidence/run.py. Phase attribution, not a speedup benchmark."""
import argparse,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence';B=C/'benchmarks/workerphases'
sys.path.insert(0,str(C/'scripts'));sys.path.insert(0,str(B))
from git_identity import require_commit,ReleasePin,verify_release_pin
from experiment_disk import DiskGuard,run_guarded
from overlay import make

def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','measure'],required=True);a=p.parse_args()
 pin=ReleasePin('v0.6.0','b57183b08d48884840111e8b53daa500734337f0','b3b3b46a8807482ad3f96725af86e031fe369b01');verify_release_pin(C,pin)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip();require_commit(C,commit);assert not subprocess.check_output(['git','status','--porcelain'],cwd=C,text=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))};env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'))
 for n in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/n).mkdir(parents=True,exist_ok=True)
 version=subprocess.check_output(['go','version'],env=env,text=True).strip();assert version=='go version go1.27.3 darwin/arm64'
 guard=DiskGuard(W,min_free_gib=16,budget_gib=8)
 src,dst=make(C,T);overlay=T/'overlay.json';save(overlay,{'Replace':{str(src):str(dst)}})
 def command(cmd,log,timeout=1200,extra=None):
  path=E/log;path.parent.mkdir(parents=True,exist_ok=True)
  with path.open('w') as f:return run_guarded(cmd,guard,cwd=C,env=dict(env,**(extra or {})),output=f,timeout=timeout)
 if a.phase=='build':
  inputs=dict(source_commit=commit,product_source_commit=pin.source_commit,tag_object_sha=pin.tag_object_sha,go=version,os=platform.mac_ver()[0],cpu='Apple M1',gomaxprocs=8,original_base_sha256=sha(src),observed_base_sha256=sha(dst),binaries={})
  for mode in ['profile','diagnostic','pprof']:
   cmd=['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true']+(['-overlay',str(overlay)] if mode=='diagnostic' else [])+['-o',str(T/'bin'/mode)]+(['cmd/pprof'] if mode=='pprof' else ['./benchmarks/workerphases/'+mode])
   assert command(cmd,'build-'+mode+'.txt')==0
   info=subprocess.check_output(['go','version','-m',T/'bin'/mode],env=env,text=True)
   if mode!='pprof':assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
   inputs['binaries'][mode]=dict(sha256=sha(T/'bin'/mode),build_info=info.replace(str(W),'<WORKSPACE>'))
   print('BUILD PASS',mode,flush=True)
  save(E/'inputs.json',inputs);return
 inputs=json.loads((E/'inputs.json').read_text());assert inputs['source_commit']==commit
 for mode,info in inputs['binaries'].items():assert sha(T/'bin'/mode)==info['sha256']
 records=[]
 def run(mode,target,rep,count,negative=False):
  name=f'{a.phase}/{rep}-{mode}-{target}'+('-negative' if negative else '');out=E/(name+'.json');profiles=E/(name+'-profiles');scratch=T/'scratch'/name;scratch.mkdir(parents=True)
  cmd=[str(T/'bin'/mode),'-out',str(out),'-target',target,'-profiles',str(profiles),'-count',str(count)]+(['-corrupt'] if negative else [])
  code=command(cmd,name+'.stderr.txt',100,dict(TMPDIR=str(scratch)))
  d=json.loads(out.read_text());assert d['cleanup'] and not any(scratch.iterdir())
  if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
  else:assert code==0 and d['success'] and d['count']==count and len(d['phases'])==3*count
  if mode=='diagnostic':
   counts=d['diagnostic'];assert sum(counts[p]['spawn']-counts[p]['exit'] for p in ['outside','fork','sql','close'])==0
  if target!='none':
   files=sorted(profiles.glob('*.pprof'));assert len(files)==(1 if negative else count)
   if not negative:
    merged=E/(name+'.pprof')
    assert command([str(T/'bin/pprof'),'-proto','-output',str(merged),str(T/'bin/profile'),*[str(p) for p in files]],name+'-merge.txt',60)==0
    for kind,flags in [('flat',[]),('cum',['-cum']),('scheduler',['-traces','-focus=runtime.pthread_cond_(signal|wait)'])]:
     assert command([str(T/'bin/pprof'),'-top' if kind!='scheduler' else '-traces','-nodecount=50','-unit=ms',*flags,str(T/'bin/profile'),str(merged)],name+'-'+kind+'.txt',60)==0
  records.append(dict(mode=mode,target=target,repetition=rep,negative=negative,count=count,report=name+'.json',returncode=code));save(E/(a.phase+'-records.json'),records);print('PASS',name,flush=True)
 if a.phase=='pilot':
  run('profile','fork',0,2);run('profile','fork',0,1,True);run('diagnostic','none',0,2);run('diagnostic','none',0,1,True)
  save(E/'pilot.json',dict(result='PASS',positive=2,negative=2))
 else:
  assert json.loads((E/'pilot.json').read_text())['result']=='PASS'
  for rep in range(2):
   run('profile','none',rep,40)
   for target in (['fork','sql','close'] if rep==0 else ['close','sql','fork']):run('profile',target,rep,40)
   run('diagnostic','none',rep,6)
  save(E/'completion.json',dict(result='PASS',profile_windows=240,control_cycles=80,diagnostic_cycles=12,queries_per_child=32,scope='phase attribution, one local host; no implementation change'))
if __name__=='__main__':main()
