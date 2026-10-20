import os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/"scripts"))
from experiment_workspace import exclusive
from experiment_disk import DiskGuard, run_guarded
root=Path.cwd().parent
env=dict(os.environ, TMPDIR=str(root/"temp/tmp"), GOTMPDIR=str(root/"temp/go-tmp"))
with exclusive(root):
    code=run_guarded(sys.argv[1:], DiskGuard(root,16,32), cwd=Path.cwd(), env=env, timeout=7200)
raise SystemExit(code)
