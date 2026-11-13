from pathlib import Path
import subprocess,os,json,hashlib
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
for n,d in [('pg',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 cmd=['go','test'];cmd+=['-overlay',str(r/'evidence/pg-overlay.json')] if n=='pg' else [];cmd+=['-c','-o',str(r/'temp'/f'{n}.test'),'./store'];print('building '+n,flush=True);subprocess.run(cmd,cwd=d,env=env,check=True)
(r/'evidence/binary-hashes.json').write_text(json.dumps({n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['pg','maria']},indent=2))
