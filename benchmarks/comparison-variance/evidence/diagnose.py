import os,sys,json,subprocess,hashlib,time,shutil
from pathlib import Path
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence';d=e/'diagnostic';d.mkdir(exist_ok=True)
sys.path.insert(0,str(r/'scripts'));from experiment_disk import DiskGuard
guard=DiskGuard(w,8,8);guard.check()
source=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect','HEAD'],cwd=r));assert source==json.loads((e/'inputs.json').read_text())['harness_identity'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
p=t/'maria-suite/internal/trace/trace.go';s=p.read_text();s=s.replace('import (','import (\n "context"\n runtimetrace "runtime/trace"');s=s.replace('start := time.Since(r.t0)','region := runtimetrace.StartRegion(context.Background(), name+":"+lane)\n\tstart := time.Since(r.t0)');s=s.replace('return func() {','return func() {\n\t\tdefer region.End()')
q=t/'trace-regions.go';q.write_text(s);overlay=t/'trace-overlay.json';overlay.write_text(json.dumps({'Replace':{str(p):str(q)}}));(d/'trace-region-source.go.txt').write_text(s)
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
for k in ['MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY','RESPONSE_PIPE','MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE','SKIP_READ_BODY','GODEBUG']:env.pop(k,None)
with (d/'build.txt').open('w')as f:
 subprocess.run(['go','build','-o',str(t/'gotrace'),'cmd/trace'],cwd=r,env=env,stdout=f,stderr=f,check=True)
 subprocess.run(['go','test','-c','-p','1','-vet=off','-overlay',str(overlay),'-o',str(t/'trace.test'),'./store'],cwd=t/'maria-suite',env=env,stdout=f,stderr=f,check=True)
(d/'inputs.json').write_text(json.dumps({'source':source,'binary_sha256':hashlib.sha256((t/'trace.test').read_bytes()).hexdigest(),'overlay_sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'limit':'8 fixed P8 processes; no repetitions after non-reproduction; diagnostics not speed comparison','reason':'2 of20 natural P8 runs have single LoadSample around487ms; no call-level identity yet; #140/#143 not declared same cause'},indent=2))
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';deadline=time.monotonic()+300
for i in range(8):
 guard.check();assert time.monotonic()<deadline
 with (d/f'run-{i}.txt').open('w')as f:subprocess.run([str(t/'trace.test'),'-test.run='+pattern,'-test.parallel=8','-test.timeout=120s','-test.trace='+str(d/f'run-{i}.trace')],cwd=t/'maria-suite',env=env|{'MODELCASE_TRACE':str(d/f'run-{i}.json')},stdout=f,stderr=f,check=True,timeout=150)
 j=json.loads((d/f'run-{i}.json').read_text());assert sum(x['name']=='test'for x in j['spans'])==70
 xs=sorted([x for x in j['spans']if x['name']=='sample'],key=lambda x:x['end_ms']-x['start_ms'],reverse=True)
 print(i,j['elapsed_ms'],xs[0],flush=True)
 # No profile parsing while a measured/diagnostic process runs.
 guard.check()
print('ALL8 DIAGNOSTIC SUITES PASS',flush=True)
