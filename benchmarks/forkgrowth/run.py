"""Copy to owned workspace evidence/run.py; stages are identity-bound and bounded."""
import argparse,hashlib,json,os,platform,shutil,subprocess,sys
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence';S=C/'benchmarks/forkgrowth'
sys.path.insert(0,str(C/'scripts'))
from git_identity import ReleasePin,require_commit,verify_release_pin

def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','measure'],required=True);phase=p.parse_args().phase
 plan=json.loads((S/'plan.json').read_text());pin=plan['source'];product=T/'product';verify_release_pin(product,ReleasePin(**pin));require_commit(product,pin['source_commit'])
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=product,text=True).strip()==pin['source_commit'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=product,text=True)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip();require_commit(C,commit);assert not subprocess.check_output(['git','status','--porcelain'],cwd=C,text=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))};env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'))
 for n in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/n).mkdir(exist_ok=True)
 go=shutil.which('go');version=subprocess.check_output([go,'version'],env=env,text=True).strip();assert version=='go version go1.27.3 darwin/arm64'
 if phase=='build':
  target=product/'internal/generatedgo/code/base/memory_mapping.go';overlay=S/'overlay/memory_mapping.go.txt';save(T/'overlay.json',dict(Replace={str(target):str(overlay)}))
  with (E/'build.txt').open('w') as log:subprocess.run([go,'build','-mod=readonly','-p','1','-trimpath','-buildvcs=true','-overlay',str(T/'overlay.json'),'-o',str(T/'bin/growth'),'./growth'],cwd=C/'benchmarks/forkattribution',env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
  info=subprocess.check_output([go,'version','-m',T/'bin/growth'],env=env,text=True);assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
  save(E/'inputs.json',dict(plan=plan,harness_source_commit=commit,go=version,host=dict(os=platform.mac_ver()[0],arch=platform.machine(),cpu='Apple M1',ram_bytes=17179869184),binary_sha256=sha(T/'bin/growth'),build_info=info,overlay=dict(target=str(target.relative_to(product)),before_sha256=sha(target),after_sha256=sha(overlay)),harness_sha256=sha(C/'benchmarks/forkattribution/growth/main.go')));print('BUILD PASS',flush=True);return
 inputs=json.loads((E/'inputs.json').read_text());assert inputs['harness_source_commit']==commit and inputs['binary_sha256']==sha(T/'bin/growth')
 records=[]
 def run(rep,negative=False):
  name=f'{phase}/run-{rep}'+('-negative' if negative else '');out=E/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True);scratch=T/'scratch'/name;scratch.mkdir(parents=True)
  cmd=[str(T/'bin/growth'),'-out',str(out)]+(['-corrupt'] if negative else [])
  with (E/(name+'.stderr.txt')).open('w') as log:code=subprocess.run(cmd,cwd=C,env=dict(env,TMPDIR=str(scratch)),stdout=log,stderr=subprocess.STDOUT,timeout=100).returncode
  d=json.loads(out.read_text());assert d['cleanup_complete'] and not any(scratch.iterdir())
  if negative:assert code!=0 and not d['success'] and 'pristine oracle' in d['error']
  else:
   assert code==0 and d['success'] and len(d['children'])==2
   for child in d['children']:
    assert child['success'] and child['cleanup_complete'] and len(child['steps'])==child['after']['grow_calls']-child['before']['grow_calls']
  records.append(dict(report=name+'.json',negative=negative,returncode=code,scratch_empty=True));save(E/(phase+'-records.json'),records);print('PASS',name,flush=True)
 if phase=='pilot':run(0);run(0,True);save(E/'pilot-result.json',dict(result='PASS',positive=1,negative=1))
 else:
  assert json.loads((E/'pilot-result.json').read_text())['result']=='PASS'
  for i in range(3):run(i)
  save(E/'completion.json',dict(result='PASS',processes=3,children=6,scope='Observed growth only; batching models not applied; no performance result'))
if __name__=='__main__':main()
