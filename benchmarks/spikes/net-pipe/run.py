"""Run the fixed #66 correctness and five-process TCP/Pipe comparison; workspace path is the sole argument."""
import hashlib,json,os,platform,re,subprocess,sys,time
from pathlib import Path
w=Path(sys.argv[1]);binary=w/'temp/host.test';e=w/'evidence';env=dict(os.environ,GOMAXPROCS='8')
metadata={'source_commit':json.loads((e/'source-identity.json').read_text())['source_commit'],'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'platform':platform.platform(),'machine':platform.machine(),'gomaxprocs':8,'driver':'github.com/go-sql-driver/mysql v1.9.3','go':'go1.26.10','vcs_stamp':'Go test binary does not contain VCS fields; clean source identities checked before compilation, binary SHA256 recorded','build_worktree_clean':True}
(e/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
def run(name,args,localenv=env):
 with (e/(name+'.txt')).open('w') as log:
  p=subprocess.run([str(binary)]+args,env=localenv,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 print(name,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
run('correctness',['-test.run','^Test','-test.v','-test.timeout','120s'])
# Probe fixed-result workload before spending the predefined five-pair budget.
run('benchmark-probe',['-test.run','^$','-test.bench','BenchmarkIssue66','-test.benchtime','1x','-test.timeout','120s'])
rows=[]
for i in range(5):
 order='tcp-first' if i%2==0 else 'pipe-first';localenv=dict(env,ISSUE66_ORDER=order)
 name='benchmark-'+str(i+1)
 run(name,['-test.run','^$','-test.bench','BenchmarkIssue66','-test.benchtime','1000x','-test.timeout','120s'],localenv)
 for line in (e/(name+'.txt')).read_text().splitlines():
  m=re.match(r'BenchmarkIssue66/(tcp|pipe)/([^\s-]+)-\d+\s+(\d+)\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op',line)
  if m:rows.append(dict(process=i+1,order=order,transport=m[1],workload=m[2],iterations=int(m[3]),ns_per_op=float(m[4]),bytes_per_op=int(m[5]),allocs_per_op=int(m[6])))
 assert len(rows)==(i+1)*8,(i,len(rows))
(e/'benchmarks.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: 5 paired processes, 40 cells',flush=True)
