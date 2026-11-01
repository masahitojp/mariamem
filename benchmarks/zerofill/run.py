"""Copied to owned evidence/run.py. Observation-only MemoryFill probe."""
import argparse,hashlib,json,os,platform,shutil,subprocess,sys
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence';B=C/'benchmarks/zerofill'
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
 guard=DiskGuard(W,min_free_gib=16,budget_gib=8);target=C/'internal/generatedgo/code/base/base.go';overlay=T/'overlay.json';save(overlay,{'Replace':{str(target):str(B/'base.go.txt')}})
 def command(cmd,log,timeout=900,extra=None):
  with (E/log).open('w') as f:r=run_guarded(cmd,guard,cwd=C,env=dict(env,**(extra or {})),output=f,timeout=timeout)
  return r
 if a.phase=='build':
  code=command(['go','build','-p','1','-mod=readonly','-trimpath','-buildvcs=true','-overlay',str(overlay),'-o',str(T/'bin/probe'),'./benchmarks/zerofill'],'build.txt',1200);assert code==0,code
  info=subprocess.check_output(['go','version','-m',T/'bin/probe'],env=env,text=True);assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
  save(E/'inputs.json',dict(source_commit=commit,baseline_source_commit=pin.source_commit,tag_object_sha=pin.tag_object_sha,go=version,os=platform.mac_ver()[0],cpu='Apple M1',ram_bytes=17179869184,gomaxprocs=8,binary_sha256=sha(T/'bin/probe'),build_info=info.replace(str(W),'<WORKSPACE>'),original_base_sha256=sha(target),overlay_sha256=sha(B/'base.go.txt')));print('BUILD PASS',flush=True);return
 inputs=json.loads((E/'inputs.json').read_text());assert inputs['source_commit']==commit and inputs['binary_sha256']==sha(T/'bin/probe')
 records=[]
 def run(observed,rep,negative=False):
  name=f'{a.phase}/{rep}-'+('observed' if observed else 'control')+('-negative' if negative else '');out=E/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True);scratch=T/'scratch'/name;scratch.mkdir(parents=True)
  cmd=[str(T/'bin/probe'),'-out',str(out)]+(['-observe'] if observed else [])+(['-corrupt'] if negative else [])
  code=command(cmd,name+'.stderr.txt',120,dict(TMPDIR=str(scratch)))
  d=json.loads(out.read_text());assert d['cleanup'] and not d['overflow'] and not any(scratch.iterdir())
  if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
  else:assert code==0 and d['success'] and len(d['phases'])==6
  if observed:assert d['totals'] and d['large_zero_events']
  else:assert not d['totals'] and not d['large_zero_events']
  records.append(dict(observed=observed,repetition=rep,negative=negative,report=name+'.json',returncode=code));save(E/(a.phase+'-records.json'),records);print('PASS',name,flush=True)
 if a.phase=='pilot':
  assert command([str(T/'bin/probe'),'-selftest'],'selftest.txt',30)==0
  for observed in [False,True]:run(observed,0);run(observed,0,True)
  save(E/'pilot.json',dict(result='PASS',selftest='PASS',positive=2,negative=2))
 else:
  assert json.loads((E/'pilot.json').read_text())['result']=='PASS'
  for i in range(3):
   for observed in ([False,True] if i%2==0 else [True,False]):run(observed,i)
  save(E/'completion.json',dict(result='PASS',pairs=3,children_per_process=2,scope='observation only; no optimization'))
if __name__=='__main__':main()
