"""Copy into owned workspace evidence/run.py. Fixed local prototype campaign."""
import argparse,hashlib,json,os,platform,select,shutil,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence';B=C/'benchmarks/bufferalignment'
sys.path.insert(0,str(C/'scripts'))
from git_identity import require_commit,ReleasePin,verify_release_pin
from experiment_disk import DiskGuard,run_guarded

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
 base=C/'internal/generatedgo/code/base/base.go';p0=C/'internal/generatedgo/code/p0/p0_pure.go'
 observed=T/'base.go';shutil.copyfile(base,observed)
 subprocess.run(['patch','--batch',str(observed),str(B/'observer.patch')],check=True,stdout=subprocess.DEVNULL)
 original=p0.read_text();needle='v2929 = Fn239(m, v2919+int32(12), int32(4096), v2928)'
 assert original.count(needle)==1
 aligned=T/'p0_pure.go';aligned.write_text(original.replace(needle,needle.replace('4096','2097152')))
 overlays={}
 for mode in ['baseline','aligned']:
  overlays[mode]=T/(mode+'-overlay.json')
  replacements={str(base):str(observed)}
  if mode=='aligned':replacements[str(p0)]=str(aligned)
  save(overlays[mode],{'Replace':replacements})

 def command(cmd,log,timeout=900):
  with (E/log).open('w') as f:r=run_guarded(cmd,guard,cwd=C,env=env,output=f,timeout=timeout)
  print(log,r,flush=True)
  # Fail closed on the guarded command status.
  assert r==0,r
  return r
 if a.phase=='build':
  inputs=dict(source_commit=commit,baseline_source_commit=pin.source_commit,tag_object_sha=pin.tag_object_sha,go=version,os=platform.mac_ver()[0],cpu='Apple M1',ram_bytes=17179869184,gomaxprocs=8,binaries={},original_base_sha256=sha(base),observed_base_sha256=sha(observed),original_p0_sha256=sha(p0),aligned_p0_sha256=sha(aligned),observer_patch_sha256=sha(B/'observer.patch'))
  for mode in ['baseline','aligned']:
   cmd=['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true']+['-overlay',str(overlays[mode])]+['-o',str(T/'bin'/mode),'./benchmarks/bufferalignment']
   command(cmd,'build-'+mode+'.txt',1200)
   info=subprocess.check_output(['go','version','-m',T/'bin'/mode],env=env,text=True);assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
   inputs['binaries'][mode]=dict(sha256=sha(T/'bin'/mode),build_info=info.replace(str(W),'<WORKSPACE>'))
  save(E/'inputs.json',inputs);return
 inputs=json.loads((E/'inputs.json').read_text());assert inputs['source_commit']==commit
 records=[]
 def run(mode,rep,negative=False):
  assert sha(T/'bin'/mode)==inputs['binaries'][mode]['sha256'];guard.check()
  name=f'{a.phase}/{rep}-{mode}'+('-negative' if negative else '');out=E/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True)
  scratch=T/'scratch'/name;scratch.mkdir(parents=True)
  cmd=[str(T/'bin'/mode),'-out',str(out)]+(['-corrupt'] if negative else [])+(['-observe'] if a.phase=='pilot' else [])
  rss={}
  with (E/(name+'.stderr.txt')).open('w') as err:
   proc=subprocess.Popen(cmd,cwd=C,env=dict(env,TMPDIR=str(scratch)),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
   try:
    deadline=time.monotonic()+100
    while True:
     assert time.monotonic()<deadline,'timeout';guard.check()
     if not select.select([proc.stdout],[],[],1)[0]:continue
     line=proc.stdout.readline()
     if not line:break
     event=json.loads(line);stage=event['checkpoint'];assert stage not in rss
     rss[stage]=int(subprocess.check_output(['ps','-o','rss=','-p',str(proc.pid)],text=True).strip())*1024
     proc.stdin.write('\n');proc.stdin.flush()
    code=proc.wait(timeout=5)
   finally:
    if proc.poll() is None:proc.kill();proc.wait()
  d=json.loads(out.read_text());assert d['cleanup'] and not any(scratch.iterdir())
  if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
  else:
   assert code==0 and d['success'] and len(d['children'])==4
   assert set(rss)=={'baseline','closed','child-1','child-2','child-3','child-4'}
  assert not d['overflow']
  assert d['final']['active_mappings']==0 and d['final']['active_rw_bytes']==0 and d['final']['active_reserved_bytes']==0
  if a.phase=='pilot' and not negative:
   for phase in range(1,5):
    events=[e for e in d['large_zero_events'] if e['phase']==phase and any(f['function'].endswith('p0.Fn18568') and f['line']==676523 for f in e['stack'])]
    assert [e['bytes'] for e in events]==([16777216,18567168] if mode=='baseline' else [16777216]),events
    if mode=='aligned':assert events[0]['dst']%2097152==0
  if a.phase=='measure':assert not d['totals'] and not d['large_zero_events']

  records.append(dict(mode=mode,repetition=rep,negative=negative,report=name+'.json',rss=rss,returncode=code));save(E/(a.phase+'-records.json'),records);print('PASS',name,flush=True)
 if a.phase=='pilot':
  for mode in ['baseline','aligned']:run(mode,0);run(mode,0,True)
  save(E/'pilot.json',dict(result='PASS',positive=2,negative=2))
 else:
  assert json.loads((E/'pilot.json').read_text())['result']=='PASS'
  for i in range(5):
   for mode in (['baseline','aligned'] if i%2==0 else ['aligned','baseline']):run(mode,i)
  save(E/'completion.json',dict(result='PASS',pairs=5,children_per_process=4,scope='macOS arm64 bounded experimental comparison'))
if __name__=='__main__':main()
