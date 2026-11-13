from pathlib import Path
import subprocess,json,os
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8');p=r/'temp/audit_witness_test.go';p.write_bytes((r/'evidence/witness_test.go.txt').read_bytes());q=r/'temp/witness-overlay.json';q.write_text(json.dumps({'Replace':{str(r/'temp/maria/store/audit_witness_test.go'):str(p)}}))
subprocess.run(['go','test','-overlay',str(q),'-c','-o',str(r/'temp/witness.test'),'./store'],cwd=r/'temp/maria',env=env,check=True)
rows=[]
for test in ['TestAuditWitness','TestStatusSecond']:
 for arm in ['0','1']:
  e=env.copy();e['MARIA_AUDIT_OF']=arm;e.pop('MODELCASE_TRACE',None);p=subprocess.run([str(r/'temp/witness.test'),'-test.v','-test.run','^'+test+'$','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);(r/f'evidence/{test}-{arm}.txt').write_text(p.stdout+p.stderr);rows.append({'test':test,'arm':arm,'returncode':p.returncode});print(p.stdout+p.stderr,flush=True)
(r/'evidence/witness-results.json').write_text(json.dumps(rows,indent=2));assert all(x['returncode']==0 for x in rows if x['test']=='TestAuditWitness'),'core firing witness failed'
