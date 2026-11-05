import os,sys,subprocess
from pathlib import Path
w=Path('.').resolve();r=w/'worktree';sys.path.insert(0,str(r/'scripts'));from build_feedback import go_environment
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w);env=go_environment({k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')});env.update(GOTOOLCHAIN='go1.26.10',GOMAXPROCS='2',CGO_ENABLED='0',GOWORK='off',GOENV='off');subprocess.run(['go','version'],env=env,check=True);subprocess.run(['go','mod','download'],cwd=r,env=env,check=True)
