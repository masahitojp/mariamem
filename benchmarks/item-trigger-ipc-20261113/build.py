from pathlib import Path
import subprocess,os,hashlib
r=Path(__file__).resolve().parents[1];e=os.environ.copy();e.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
subprocess.run(['go','test','-overlay',str(r/'evidence/overlay.json'),'-c','-o',str(r/'temp/maria.test'),'./store'],cwd=r/'temp/maria',env=e,check=True)
(r/'evidence/binary.sha256').write_text(hashlib.sha256((r/'temp/maria.test').read_bytes()).hexdigest()+'\n')
