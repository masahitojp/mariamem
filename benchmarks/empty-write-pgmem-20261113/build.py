from pathlib import Path
import os,subprocess,json,hashlib
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
for name,d in [('pgmem',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 cmd=['go','test']
 if name=='maria':cmd+=['-overlay',str(r/'evidence/overlay.json')]
 cmd+=['-c','-o',str(r/'temp'/f'{name}.test'),'./store'];subprocess.run(cmd,cwd=d,env=e,check=True)
(r/'evidence/binary-hashes.json').write_text(json.dumps({n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['pgmem','maria']},indent=2))
