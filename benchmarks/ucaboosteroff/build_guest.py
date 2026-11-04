import json,subprocess,sys,time
from pathlib import Path
w=Path(sys.argv[1]).resolve();cmd=json.loads((w/'evidence/build-command.json').read_text());start=time.time()
with (w/'evidence/guest-build.log').open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
(w/'evidence/build-exit.json').write_text(json.dumps({'exit_code':p.returncode,'wall_seconds':time.time()-start})+'\n')
raise SystemExit(p.returncode)
