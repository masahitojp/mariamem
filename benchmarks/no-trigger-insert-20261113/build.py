from pathlib import Path
import subprocess,os,json,hashlib
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8')
sources=list((r/'temp/maria/store').glob('*.go'))+list((r/'temp/pgmem/bench/modelcase/store').glob('*.go'))
before={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
for n,d in [('pg',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 print('building '+n,flush=True);subprocess.run(['go','test','-c','-o',str(r/'temp'/f'{n}.test'),'./store'],cwd=d,env=env,check=True)
(r/'evidence/binary-hashes.json').write_text(json.dumps({n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['pg','maria']},indent=2))

assert before=={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(r/"evidence/build-source-hashes.json").write_text(json.dumps(before,indent=2))
