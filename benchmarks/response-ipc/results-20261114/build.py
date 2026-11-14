from pathlib import Path
import subprocess,os
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';(T/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
with (E/'build.txt').open('w')as f:subprocess.run(['go','test','-c','-vet=off','-p','1','-overlay',str(E/'overlay.json'),'-o',str(T/'probe'),'./store'],cwd=T/'maria',env=env,stdout=f,stderr=f,check=True,timeout=1200)
print('BUILD PASS',flush=True)
