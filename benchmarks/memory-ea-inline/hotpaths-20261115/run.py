from pathlib import Path
import os,subprocess,json,hashlib,tarfile,re,time,resource
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1')
for k in ['MODELCASE_DSN','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY']:env.pop(k,None)
def run(name,cmd,cwd=S,timeout=1200):
 a=time.monotonic()
 with (E/(name+'.txt')).open('w')as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=timeout)
 print(name,'PASS',round(time.monotonic()-a,2),flush=True)
j=json.loads(subprocess.check_output(['python3',S/'scripts/git_identity.py','--root',S,'inspect','HEAD']));assert j['source_commit']=='523a8883d434af381f7a9d00a2c6ae571eefc172';(E/'source.json').write_text(json.dumps(j,indent=2))
run('toolchain',['go','version'])
with tarfile.open(S/'benchmarks/memory-ea-inline/suite-20261115/harness.tar.gz')as a:a.extractall(T,filter='data')
p=T/'maria-suite/go.mod';p.write_text(re.sub(r'(?m)^go .*$', 'go 1.26.0',p.read_text()).replace('<PRODUCT_WORKTREE>',str(S)))
run('lower-build',['go','build','-o',T/'lower',S/'benchmarks/memory-ea-inline/shared-lowering-20261115/lower.go'])
mp={}
for pkg,fn,h in [('p3','Fn13460','63009c1d79f292d391640f27ef98c443441a7cf1dbe453d63ac98b47757d596f'),('p1','Fn15594','65aeac005aaf658052b0ec37978d1f6b5b2a87308a06fdd782ff01f48ed257ee')]:
 src=S/f'internal/generatedgo/code/{pkg}/{pkg}_pure.go';dst=T/(pkg+'.go');run('lower-'+pkg,[T/'lower',src,dst,fn]);assert hashlib.sha256(dst.read_bytes()).hexdigest()==h;mp[str(src)]=str(dst)
(E/'shared-overlay.json').write_text(json.dumps({'Replace':mp}))
p=S/'internal/generatedgo/code/base/base.go';x=p.read_text();a='\t\tWasm_trap_memory_oob()';assert x.count(a)==1;x=x.replace(a,'\t\tpanic("wasm: memory access out of bounds")');a='\n//go:noinline\nfunc Wasm_trap_memory_oob() { panic("wasm: memory access out of bounds") }\n';assert x.count(a)==1;x=x.replace(a,'');dst=T/'direct-base.go';dst.write_text(x);assert hashlib.sha256(dst.read_bytes()).hexdigest()=='0170988abb28903ff3824a0e5efbe7865b0ba4961a892de7ce5bfca842ba332a';(E/'direct-overlay.json').write_text(json.dumps({'Replace':{str(p):str(dst)}}))
binaries={}
for label in ['baseline','direct','shared']:
 extra=[]if label=='baseline'else['-overlay',E/(label+'-overlay.json')]
 run(label+'-build',['go','test','-c','-vet=off','-p','1',*extra,'-o',T/(label+'.test'),'./store'],cwd=T/'maria-suite')
 b=T/(label+'.test');binaries[label]={'bytes':b.stat().st_size,'sha256':hashlib.sha256(b.read_bytes()).hexdigest()}
(E/'binaries.json').write_text(json.dumps(binaries,indent=2))
pattern='^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$';records=[]
for label in ['baseline','direct','shared']:
 env['MODELCASE_TRACE']=str(E/(label+'-trace.json'));before=resource.getrusage(resource.RUSAGE_CHILDREN);a=time.monotonic()
 run(label+'-profile',[T/(label+'.test'),'-test.run='+pattern,'-test.parallel=1','-test.count=20','-test.timeout=120s','-test.cpuprofile='+str(E/(label+'.pprof'))],cwd=T/'maria-suite',timeout=180)
 after=resource.getrusage(resource.RUSAGE_CHILDREN);r={'label':label,'wall_s':time.monotonic()-a,'cpu_s':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime};j=json.loads((E/(label+'-trace.json')).read_text());r['elapsed_ms']=j['elapsed_ms'];r['counts']={k:sum(s['name']==k for s in j['spans'])for k in ['test','fork','sample']};assert r['counts']=={'test':1400,'fork':400,'sample':401};records.append(r)
(E/'records.json').write_text(json.dumps(records,indent=2))
for label in ['baseline','direct','shared']:
 for kind,flags in [('flat',['-top','-nodecount=80']),('cum',['-top','-cum','-nodecount=80']),('callers',['-peek=MemoryEA']),('physical',['-top','-noinlines','-nodecount=80']),('raw',['-raw'])]:
  run(label+'-'+kind,['go','tool','pprof',*flags,T/(label+'.test'),E/(label+'.pprof')],timeout=120)
