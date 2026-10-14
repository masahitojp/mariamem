from pathlib import Path
import json,sys
w=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(w/'temp/source/scripts'))
from experiment_disk import DiskGuard,run_guarded
guard=DiskGuard(w,8,6)
# This clone contains repository history; avoid frequent tree scans alongside
# timed runs. Still check free space and growth before/during/after the campaign.
with (w/'evidence/campaign-console.txt').open('w') as log:
    code=run_guarded([sys.executable,str(w/'temp/campaign.py')],guard,cwd=w/'temp/source',
                     output=log,interval=5,timeout=1200)
(w/'evidence/campaign-guard.json').write_text(json.dumps(dict(returncode=code,
    interval_seconds=5,timeout_seconds=1200,peak_owned_bytes=guard.peak,
    minimum_free_bytes=guard.minimum_free),indent=2)+'\n')
print('campaign exit',code,flush=True)
sys.exit(code)
