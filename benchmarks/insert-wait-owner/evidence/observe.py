from pathlib import Path
import os,sys,json,subprocess,shutil,re,hashlib,time
w=Path(__file__).resolve().parent.parent;r=w/'worktree';t=w/'temp';e=w/'evidence'
sys.path.insert(0,str(r/'scripts'));from experiment_disk import DiskGuard
g=DiskGuard(w,8,6);g.check()
identity=json.loads(subprocess.check_output([sys.executable,str(r/'scripts/git_identity.py'),'--root',str(r),'inspect','HEAD']));assert identity['source_commit']=='dc2dbf37ff5b70104d3c434cdfda612a0654ae9b';assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
src=r/'benchmarks/comparison-variance/harness/maria-suite';dst=t/'suite';shutil.copytree(src,dst,dirs_exist_ok=True);p=dst/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)))
over={};sites={16784:'page_wait',18171:'page_complete',18277:'read_callback',16602:'submit',16583:'task_execute',16600:'maintenance',16594:'add_thread'}
for p in (r/'internal/generatedgo/code').glob('p*/*pure.go'):
 s=p.read_text();used=False
 for n,label in sites.items():
  pattern=r'(func Fn'+str(n)+r'\(m \*base.Module, ([^\n]+)\) [^{]*\{)';match=re.search(pattern,s)
  if not match:continue
  args=re.findall(r'(l\d+) int32',match[2]);fmt=' '.join(x+'=%d'for x in args);params=', '.join(args)
  code=f'\n trace.Logf(context.Background(), "owner", "{label}_begin module=%p {fmt}", m.M, {params})\n defer trace.Logf(context.Background(), "owner", "{label}_end module=%p {fmt}", m.M, {params})\n'
  s=s[:match.end()]+code+s[match.end():];used=True
 if used:
  s=s.replace('import (','import (\n"context"\n"runtime/trace"');q=t/(p.parent.name+'-overlay.go');q.write_text(s);over[str(p)]=str(q)
p=r/'internal/generatedgo/main.go';s=p.read_text();s=s.replace('import (','import (\n rttrace "runtime/trace"')
# context already imported by generatedgo/main.go
s=s.replace('rc := base.AtomicWait32At(m, uint64(addr), expected, duration)','rttrace.Logf(context.Background(), "owner", "futex_wait_begin module=%p addr=%d expected=%d timeout=%d", m.M, addr, expected, duration)\n rc := base.AtomicWait32At(m, uint64(addr), expected, duration)\n rttrace.Logf(context.Background(), "owner", "futex_wait_end module=%p addr=%d rc=%d", m.M, addr, rc)')
s=s.replace('base.AtomicNotify(m, addr, 0, count)','rttrace.Logf(context.Background(), "owner", "futex_wake module=%p addr=%d count=%d", m.M, addr, count)\n base.AtomicNotify(m, addr, 0, count)')
q=t/'main-overlay.go';q.write_text(s);over[str(p)]=str(q)
p=dst/'internal/trace/trace.go';s=p.read_text().replace('import (','import (\n "context"\n runtimetrace "runtime/trace"').replace('start := time.Since(r.t0)','region := runtimetrace.StartRegion(context.Background(), name+":"+lane)\n start := time.Since(r.t0)').replace('return func() {','return func() {\n defer region.End()');q=t/'regions.go';q.write_text(s);over[str(p)]=str(q)
(t/'overlay.json').write_text(json.dumps({'Replace':over}));(e/'overlays').mkdir(exist_ok=True)
(e/'overlay-hashes.json').write_text(json.dumps({str(Path(k).relative_to(r)) if str(k).startswith(str(r)) else str(k): {'original_sha256':hashlib.sha256(Path(k).read_bytes()).hexdigest(),'overlay_sha256':hashlib.sha256(Path(v).read_bytes()).hexdigest()} for k,v in over.items()},indent=2))
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOWORK='off',GOENV='off',GOFLAGS='',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
for k in ['GODEBUG','MODELCASE_DSN','SKIP_READ_BODY','TRIGGERS_OFF','SUM_EXPERIMENT','SAMPLE_PROFILE','PROFILE_DIR','INSERT_STAGES','PROFILE_ONLY','RESPONSE_PIPE']:env.pop(k,None)
with (e/'build.txt').open('w')as f:subprocess.run(['go','test','-c','-p','1','-vet=off','-overlay',str(t/'overlay.json'),'-o',str(t/'observe.test'),'./store'],cwd=dst,env=env,stdout=f,stderr=f,check=True)
(e/'inputs.json').write_text(json.dumps({'source_identity':identity,'product_source_commit':'6558ee8fb2211313a8aa0ea6070ac5256767811a','guest_sha256':'77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450','binary_sha256':hashlib.sha256((t/'observe.test').read_bytes()).hexdigest(),'sites':sites,'limit':'8 fixed P8 suites, no repeats, no performance claim','buildinfo':subprocess.check_output(['go','version','-m',str(t/'observe.test')],env=env,text=True)},indent=2))
print('BUILD_COMPLETE',flush=True)
if '--build-only' in sys.argv:sys.exit(0)
