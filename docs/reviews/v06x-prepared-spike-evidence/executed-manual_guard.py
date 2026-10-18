import sys,os
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'scripts'))
from experiment_workspace import exclusive
from experiment_disk import DiskGuard,run_guarded
root=Path.cwd().parent
for name in ("tmp", "go-tmp"):(root/"temp"/name).mkdir(exist_ok=True)
env=dict(os.environ,TMPDIR=str(root/"temp/tmp"),GOTMPDIR=str(root/"temp/go-tmp"),MARIAMEM_EXPERIMENT_TEMP=str(root/"temp"),MARIAMEM_EXPERIMENT_EVIDENCE=str(root/"evidence"))
with exclusive(root):
    code=run_guarded(sys.argv[1:],DiskGuard(root,16,32),cwd=Path.cwd(),env=env,timeout=7200)
sys.exit(code)
