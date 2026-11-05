"""Run one fixed three-process database/sql transport comparison."""
import csv,hashlib,json,os,platform,re,statistics,subprocess,sys
from pathlib import Path
w=Path(sys.argv[1]);e=w/'evidence';d=w/'worktree/benchmarks/transport-compare';binary=w/'temp/compare.test';rows=[]
env=dict(os.environ,GOMAXPROCS='8',GOGC='100');env.pop('GOMEMLIMIT',None)
for i in range(1,4):
 order='reverse' if i==2 else 'forward'
 with (e/f'process-{i}.txt').open('w') as log:
  p=subprocess.run([str(binary),'-test.run','^$','-test.bench','BenchmarkCompare','-test.benchtime','500x','-test.timeout','120s'],env=dict(env,COMPARE_ORDER=order),stdout=log,stderr=subprocess.STDOUT,timeout=180)
 if p.returncode:raise SystemExit(f'process{i}: FAIL exit{p.returncode}')
 for line in (e/f'process-{i}.txt').read_text().splitlines():
  m=re.match(r'BenchmarkCompare/(maria|pgmem)/(tcp|pipe)/([^\s-]+)-\d+\s+(\d+)\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op',line)
  if m:rows.append(dict(process=i,order=order,engine=m[1],transport=m[2],workload=m[3],iterations=int(m[4]),ns_per_op=float(m[5]),bytes_per_op=int(m[6]),allocs_per_op=int(m[7])))
 assert len(rows)==i*16,(i,len(rows))
 print(f'process{i}: 16 cells PASS',flush=True)
assert all(r['iterations']==500 for r in rows)
summary=[]
for work in dict.fromkeys(r['workload'] for r in rows):
 entry={'workload':work}
 for engine in ['maria','pgmem']:
  for mode in ['tcp','pipe']:
   rs=[r for r in rows if r['engine']==engine and r['transport']==mode and r['workload']==work];assert len(rs)==3
   entry[engine+'_'+mode]={key:statistics.median(r[key] for r in rs) for key in ['ns_per_op','bytes_per_op','allocs_per_op']}
 summary.append(entry)
meta={'mariamem_baseline_source_commit':'676515eb9244fc501b5a600791b0cf0a6174fecd','harness_source_commit':json.loads((e/'source-identity.json').read_text())['source_commit'],'pgmem_release':json.loads((e/'pgmem-identity.json').read_text()),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'toolchain':'go1.26.10','platform':platform.platform(),'gomaxprocs':8,'gogc':100,'iterations':500,'processes':3,'result':'48 cells PASS','drivers':{'mysql':'1.9.3','pgx':'5.11.0'},'pgx_mode':'SimpleProtocol for nonprepared SQL; explicit database/sql Prepare uses server prepared statements','binary_vcs_stamp':'not present for test binary; both source identities validated before build and binary hash retained'}
for name,v in [('results.json',rows),('summary.json',summary),('metadata.json',meta)]:
 text=json.dumps(v,indent=2)+'\n';(d/name).write_text(text);(e/name).write_text(text)
with (d/'results.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
for s in summary:print(s,flush=True)
