"""Fixed lightweight main API measurement; takes the absolute owned workspace."""
import csv,hashlib,json,os,platform,re,statistics,subprocess,sys
from pathlib import Path
w=Path(sys.argv[1]);binary=w/'temp/pipe.test';e=w/'evidence';target=w/'worktree/benchmarks/pipe-transport'
env=dict(os.environ,GOMAXPROCS='8',GOGC='100');env.pop('GOMEMLIMIT',None)
rows=[]
for process in range(1,4):
 order='pipe-first' if process==2 else 'tcp-first'
 with (e/f'process-{process}.txt').open('w') as log:
  p=subprocess.run([str(binary),'-test.run','^$','-test.bench','BenchmarkPipeTransport','-test.benchtime','500x','-test.timeout','120s'],env=dict(env,ISSUE66_ORDER=order),stdout=log,stderr=subprocess.STDOUT,timeout=180)
 if p.returncode:raise SystemExit(f'process{process} failed: {p.returncode}')
 for line in (e/f'process-{process}.txt').read_text().splitlines():
  m=re.match(r'BenchmarkPipeTransport/(tcp|pipe)/([^\s-]+)-\d+\s+(\d+)\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op',line)
  if m:rows.append(dict(process=process,order=order,transport=m[1],workload=m[2],iterations=int(m[3]),ns_per_op=float(m[4]),bytes_per_op=int(m[5]),allocs_per_op=int(m[6])))
 assert len(rows)==process*8,(process,len(rows))
 print(f'process{process}: 8 cells PASS',flush=True)
assert all(r['iterations']==500 for r in rows)
summary=[]
for work in dict.fromkeys(r['workload'] for r in rows):
 groups={m:[r for r in rows if r['workload']==work and r['transport']==m] for m in ['tcp','pipe']}
 v={m:{field:statistics.median(r[field] for r in rs) for field in ['ns_per_op','bytes_per_op','allocs_per_op']} for m,rs in groups.items()}
 summary.append(dict(workload=work,tcp=v['tcp'],pipe=v['pipe'],elapsed_reduction_percent=round(100*(1-v['pipe']['ns_per_op']/v['tcp']['ns_per_op']),2)))
meta={'baseline_source_commit':'676515eb9244fc501b5a600791b0cf0a6174fecd','measured_source_commit':json.loads((e/'source-identity.json').read_text())['source_commit'],'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'go':'1.26.10','platform':platform.platform(),'machine':platform.machine(),'gomaxprocs':8,'gogc':100,'driver':'mysql1.9.3','fresh_processes':3,'iterations_per_cell':500,'result':'24 cells PASS','test_binary_vcs_stamp':'not present; clean source identity checked before build, binary hash retained'}
for n,v in [('results.json',rows),('summary.json',summary),('metadata.json',meta)]:
 text=json.dumps(v,indent=2)+'\n';(target/n).write_text(text);(e/n).write_text(text)
with (target/'results.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
for r in summary:print(r,flush=True)
