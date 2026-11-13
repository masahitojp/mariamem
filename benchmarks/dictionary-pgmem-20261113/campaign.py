from pathlib import Path
import dataclasses,hashlib,json,os,subprocess,sys
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence'
R=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
sys.path.insert(0,str(R/'scripts'))
from git_identity import require_commit,verify_release_pin,ReleasePin
from experiment_disk import DiskGuard,run_guarded
guard=DiskGuard(W,12,12)
plan=json.loads((E/'plan.json').read_text())
def run(args,cwd=None):
 code=run_guarded(list(map(str,args)),guard,cwd=cwd or T,timeout=1200)
 assert code==0,(args,code)
def git(d,*args):return subprocess.check_output(['git',*args],cwd=d,text=True).strip()
identities={}
for label,sha in [('harness',plan['harness_source_commit'])]+[(n,v['source_commit']) for n,v in plan['products'].items() if n!='pgmem']:
 require_commit(R,sha)
 run(['git','clone','--shared','--no-checkout',R,T/label])
 run(['git','checkout','--detach',sha],T/label)
 assert not git(T/label,'status','--porcelain')
 identities[label]=dataclasses.asdict(require_commit(T/label,sha))
run(['git','clone','--depth','1','--branch','v1.18.2','https://github.com/shibukawa/pgmem.git',T/'pgmem'])
pin=ReleasePin(**plan['products']['pgmem'])
identities['pgmem']=dataclasses.asdict(verify_release_pin(T/'pgmem',pin))
assert git(T/'pgmem','rev-parse','HEAD')==pin.source_commit and not git(T/'pgmem','status','--porcelain')
rows=git(T/'pgmem','ls-remote','origin','refs/tags/v1.18.2','refs/tags/v1.18.2^{}').splitlines()
assert {row.split()[0] for row in rows}=={pin.source_commit,pin.tag_object_sha}
(E/'source-identity.json').write_text(json.dumps(identities,indent=2)+'\n')
(E/'upstream-preservation.json').write_text(json.dumps({'remote':'https://github.com/shibukawa/pgmem.git',**plan['products']['pgmem'],'verified_remote_tag_and_peeled_commit':True,'clean_checkout':True,'unique_edits':False},indent=2)+'\n')
for stage in ['build.py','run.py']:
 print('START '+stage,flush=True)
 run([sys.executable,E/stage])
print('CAMPAIGN COMPLETE',flush=True)
