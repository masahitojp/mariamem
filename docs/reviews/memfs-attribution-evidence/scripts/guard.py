from pathlib import Path
import json,sys
w=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(w/'temp/control/scripts'))
from experiment_disk import DiskGuard,run_guarded
g=DiskGuard(w,8,6)
mode=sys.argv[1] if len(sys.argv)>1 else ''
assert mode in ('','timer','events')
suffix=mode+'-' if mode else ''
script={'':'run.py','timer':'timer.py','events':'events.py'}[mode]
with (w/('evidence/'+suffix+'console.txt')).open('w') as log:
 code=run_guarded([sys.executable,str(w/'temp'/script)],g,cwd=w/'temp/control',output=log,interval=5,timeout=3600)
(w/('evidence/'+suffix+'guard.json')).write_text(json.dumps(dict(returncode=code,peak_owned_bytes=g.peak,minimum_free_bytes=g.minimum_free,interval_seconds=5,timeout_seconds=3600),indent=2)+'\n')
sys.exit(code)
