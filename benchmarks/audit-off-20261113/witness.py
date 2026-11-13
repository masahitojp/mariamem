from pathlib import Path
import subprocess,json,os
r=Path(__file__).resolve().parents[1];env=os.environ.copy();env.update(GOCACHE=str(r/'temp/gocache'),GOMODCACHE=str(r/'temp/modcache'),CGO_ENABLED='0',GOMAXPROCS='8',MARIA_AUDIT_OF='1',MODELCASE_MATCHED='1');results=[]
for engine,d in [('pg',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]:
 p=r/'temp'/f'{engine}_witness_test.go';p.write_bytes((r/'evidence/witness_test.go.txt').read_bytes());overlay=r/'temp'/f'{engine}-witness.json';overlay.write_text(json.dumps({'Replace':{str(d/'store/audit_off_witness_test.go'):str(p)}}));binary=r/'temp'/f'{engine}-witness.test';subprocess.run(['go','test','-overlay',str(overlay),'-c','-o',str(binary),'./store'],cwd=d,env=env,check=True)
 for arm in ['0','1']:
  e=env.copy();e.update(WITNESS_ENGINE=engine,AUDIT_OFF=arm,MODELCASE_TRACE=str(r/f'evidence/witness-{engine}-{arm}-trace.json'));p=subprocess.run([str(binary),'-test.v','-test.run','^TestAuditOffWitness$','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);(r/f'evidence/witness-{engine}-{arm}.txt').write_text(p.stdout+p.stderr);results.append({'engine':engine,'audit_off':arm,'returncode':p.returncode});print(p.stdout+p.stderr,flush=True)
  if p.returncode:break
(r/'evidence/witness-results.json').write_text(json.dumps(results,indent=2));assert len(results)==4 and all(x['returncode']==0 for x in results)
