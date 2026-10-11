"""Reproduce one guarded stage; keep logs for reduction, clean only after preservation."""
import json,sys,time,subprocess
from pathlib import Path
work=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(work/'worktree/scripts'))
from experiment_disk import DiskGuard,run_guarded
stage=sys.argv[1]
guard=DiskGuard(work,min_free_gib=20,budget_gib=24)
start=time.monotonic(); result={}
try:
    with (work/'evidence'/f'{stage}.log').open('w') as log:
        code=run_guarded(['bash',str(work/'evidence'/f'{stage}-command.sh')],guard,
                         cwd=work/'worktree',output=log,timeout=300 if stage=="acceptance" else 2400)
    result['exit']=code
finally:
    if stage=='guest':
        # Stopping the Docker client alone does not stop its daemon-owned container.
        live=subprocess.check_output(['docker','ps','--filter','name=^mariamem-v05-preview-guest$','--format','{{.Names}}'],text=True).strip()
        if live: subprocess.run(['docker','stop','mariamem-v05-preview-guest'],check=True)
    result.update(wall_seconds=time.monotonic()-start,peak_owned_bytes=guard.peak,
                  minimum_free_bytes=guard.minimum_free)
    (work/'evidence'/f'{stage}-guard.json').write_text(json.dumps(result,indent=2)+'\n')
sys.exit(code)
