from pathlib import Path
import json
import sys

work = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(work/'temp/source/scripts'))
from experiment_disk import DiskGuard,run_guarded
guard = DiskGuard(work,8,6)
with (work/'evidence/console.txt').open('w') as log:
    code = run_guarded([sys.executable,str(work/'temp/recheck.py')],guard,
                       cwd=work/'temp/source',output=log,interval=5,timeout=2400)
(work/'evidence/guard.json').write_text(json.dumps(dict(returncode=code,interval_seconds=5,
    timeout_seconds=2400,peak_owned_bytes=guard.peak,minimum_free_bytes=guard.minimum_free),indent=2)+'\n')
sys.exit(code)
