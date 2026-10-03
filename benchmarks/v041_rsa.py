#!/usr/bin/env python3
"""Released RSA configuration audit + independent-process startup samples.
Run under the shared exclusive measurement lock. No ON/OFF comparison is claimed.
"""
import argparse,hashlib,json,os,platform,statistics,subprocess,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--runs',type=int,default=30);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',MARIAMEM_RUNTIME='',MARIAMEM_NATIVE_DIR='')
binary=a.work/'rsa-probe';subprocess.run(['go','build','-o',str(binary),'./benchmarks/v041rsa'],cwd=root,env=env,check=True)
r=subprocess.run([str(binary),'auth-check'],env=env,capture_output=True,text=True,timeout=60);(a.work/'auth-check.stdout').write_text(r.stdout);(a.work/'auth-check.stderr').write_text(r.stderr)
assert r.returncode==0 and '"generated":false' in r.stdout and '"actual_callback":true' in r.stdout,(r.returncode,r.stdout,r.stderr[-2000:])
rows=[]
for i in range(a.runs):
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=60);assert r.returncode==0,(r.returncode,r.stderr);rows.append(json.loads(r.stdout));print('RSA released-OFF trial',i+1,flush=True)
def stats(k):
 v=sorted(row[k] for row in rows);return dict(min=v[0],p50=statistics.median(v),p95=v[max(0,__import__('math').ceil(.95*len(v))-1)],max=v[-1])
# Decode only the generated initial data declaration to establish artifact evidence.
s=(root/'internal/generatedgo/code/generated.go').read_text();marker='var wasm2goData_data_bin = []byte("';literal=s.split(marker,1)[1].split('")',1)[0];data=bytes.fromhex(literal.replace('\\x',''))
option=b'--caching-sha2-password-auto-generate-rsa-keys=OFF';assert option in data
record=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),base_tag='v0.4.0',go=subprocess.check_output(['go','version'],env=env,text=True).strip(),os=platform.platform(),arch=platform.machine(),runs=a.runs,rsa_off_occurrences=data.count(option),generated_data_sha256=hashlib.sha256(data).hexdigest(),guest_sha256=json.loads((root/'internal/generatedgo/provenance.json').read_text())['guest_sha256'],auth_callback='PASS, generated=false, actual_callback=true',stats={k:stats(k) for k in ['ready_seconds','first_sql_seconds','ready_cpu_seconds','first_sql_cpu_seconds']},trials=rows)
(a.work/'rsa.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record['stats'],indent=2))
