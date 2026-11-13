import os,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1]
e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
for name,d in [('pgmem',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 subprocess.run(['go','mod','tidy'],cwd=d,env=e,check=True)
 subprocess.run(['go','test','-c','-o',str(r/'temp'/f'{name}.test'),'./store'],cwd=d,env=e,check=True)
