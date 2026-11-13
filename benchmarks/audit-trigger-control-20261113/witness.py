from pathlib import Path
import subprocess,json,os
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8');o=json.loads((r/'evidence/pg-overlay.json').read_text());p=r/'temp/audit_witness_test.go';p.write_bytes((r/'evidence/witness_test.go.txt').read_bytes());o['Replace'][str(r/'temp/pgmem/bench/modelcase/store/audit_witness_test.go')]=str(p);q=r/'temp/witness-overlay.json';q.write_text(json.dumps(o))
subprocess.run(['go','test','-overlay',str(q),'-c','-o',str(r/'temp/witness.test'),'./store'],cwd=r/'temp/pgmem/bench/modelcase',env=env,check=True)
for arm in ['0','1']:
 e=env.copy();e['AUDIT_ALL_UPDATES']=arm;e.pop('MODELCASE_TRACE',None);p=subprocess.run([str(r/'temp/witness.test'),'-test.v','-test.run','^TestAuditWitness$','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);(r/f'evidence/witness-{arm}.txt').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True);assert p.returncode==0
