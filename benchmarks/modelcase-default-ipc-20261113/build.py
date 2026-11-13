from pathlib import Path
import subprocess,os,json
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
for n,d in [('pgmem',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 subprocess.run(['go','test','-c','-o',str(r/'temp'/f'{n}.test'),'./store'],cwd=d,env=e,check=True)
