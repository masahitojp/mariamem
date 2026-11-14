from pathlib import Path
import os,subprocess,json,hashlib
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence'
(T/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
for name in ['maria-suite','pg-suite']:
 with (E/(name+'-build.txt')).open('w')as f:subprocess.run(['go','test','-mod=mod','-vet=off','-c','-p','1','-o',str(T/name/'probe'),'./store'],cwd=T/name,env=env,stdout=f,stderr=f,check=True,timeout=1200)
 print('BUILT',name,flush=True)
