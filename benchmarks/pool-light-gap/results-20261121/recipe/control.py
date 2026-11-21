import os,sys,subprocess
from pathlib import Path
w=Path(sys.argv[1]).resolve()
env=dict(os.environ,TMPDIR=str(w/'temp/gotmp'),GOCACHE=str(w/'temp/gocache'),GOPROXY='off',GOWORK='off',GOTOOLCHAIN='local')
subprocess.run(['go','test','-p','1','-count=1','-run','^TestLightDetector$','-v','./period'],cwd=w/'temp/current',env=env,check=True)
