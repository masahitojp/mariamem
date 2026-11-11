from pathlib import Path
import subprocess,sys
W=Path(__file__).resolve().parents[1];B=W.parent/'timer-measure-baseline'
for target in (W,B):
 code="from pathlib import Path;import sys;sys.path.insert(0,'scripts');from dev_guest import verify_guest;from git_identity import require_commit;import subprocess;r=verify_guest(Path.cwd(),Path(sys.argv[1]));require_commit(Path.cwd(),subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip());print(r['guest_sha256'])"
 subprocess.run([sys.executable,'-c',code,str(target/'temp/guest')],cwd=target/'worktree',check=True)
