from pathlib import Path
import os,subprocess,json,hashlib
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8');sources=list((r/'temp/maria/store').glob('*.go'))+list((r/'temp/pgmem/bench/modelcase/store').glob('*.go'))+[r/'temp/go_mysql_driver_overlay.go',r/'temp/go_mysql_stmt_overlay.go'];before={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
for n,d in [('pg',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 print('building '+n,flush=True);cmd=['go','test'];cmd+=['-overlay',str(r/'evidence/overlay.json'),'-ldflags','-X github.com/go-mysql-org/go-mysql/driver.driverName=benchmark-go-mysql'] if n=='maria' else [];cmd+=['-c','-o',str(r/'temp'/f'{n}.test'),'./store'];subprocess.run(cmd,cwd=d,env=env,check=True)
assert before=={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(r/'evidence/build-source-hashes.json').write_text(json.dumps(before,indent=2));(r/'evidence/binary-hashes.json').write_text(json.dumps({n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['pg','maria']},indent=2))
(r/'evidence/go-mysql-download.json').write_bytes(subprocess.check_output(['go','mod','download','-json','github.com/go-mysql-org/go-mysql@v1.16.0'],cwd=r/'temp/maria',env=env));(r/'evidence/maria-modules.txt').write_bytes(subprocess.check_output(['go','list','-m','all'],cwd=r/'temp/maria',env=env))
