from pathlib import Path
import json,subprocess,hashlib,zipfile,sys,importlib.util
W=Path(__file__).resolve().parents[1]; B=W.parent/'timer-measure-baseline'; E=W/'evidence'
base='repos/masahitojp/mariamem/actions'
for tail,name in [('runs/42928025946','run'),('runs/42928025946/jobs','jobs'),('runs/42928025946/artifacts','artifacts')]:
 (E/(name+'.json')).write_bytes(subprocess.check_output(['gh','api',base+'/'+tail]))
for target,ident,name,expected in [(W,13814809081,'guest','2f99c67b79caae6a7cc8bee87fc820f3bebd783efb1c26a4e46d3bec9d556342'),(W,13815456820,'ci-evidence','014463a447a4951ccaba4497c0907c5e4d2304e91cb4f70c93f61cf1b43c4193'),(B,13810237295,'guest','2b4e877949d18deb84e89f19cce46e96724efdc152d7aeef319de1cc87df057e')]:
 p=target/'temp'/(name+'.zip')
 with p.open('wb') as f: subprocess.run(['gh','api',base+'/artifacts/'+str(ident)+'/zip'],stdout=f,check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
 with zipfile.ZipFile(p) as z:
  assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist());z.extractall(target/'temp'/name)
 print(name,ident,'checksum PASS',flush=True)
for target in (W,B):
 code="from pathlib import Path;import sys;sys.path.insert(0,'scripts');from dev_guest import verify_guest;from git_identity import require_commit;import subprocess;r=verify_guest(Path.cwd(),Path(sys.argv[1]));require_commit(Path.cwd(),subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip());print(r['guest_sha256'])"
 subprocess.run([sys.executable,'-c',code,str(target/'temp/guest')],cwd=target/'worktree',check=True)
