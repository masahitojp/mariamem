"""Apply the approved time, space and free-disk envelope to a phase command."""
from pathlib import Path
import sys

workspace=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(workspace/'worktree/scripts'))
from experiment_disk import DiskGuard, run_guarded

guard=DiskGuard(workspace,min_free_gib=8,budget_gib=8)
try:
    code=run_guarded(sys.argv[3:],guard,timeout=int(sys.argv[2]),interval=3)
finally:
    print('peak owned bytes',guard.peak,'minimum free bytes',guard.minimum_free,flush=True)
raise SystemExit(code)
