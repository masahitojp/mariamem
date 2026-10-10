import os,sys,time,json,subprocess,hashlib
from pathlib import Path
r=Path.cwd();w=r.parent;t=w/'temp';e=w/'evidence';sys.path.insert(0,str(r/'scripts'))
from experiment_disk import DiskGuard,run_guarded
from git_identity import require_commit
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();require_commit(r,sha)
compilers={'1268':Path(os.environ['GO1268_BIN']),'1272':t/'sdk1272/go/bin/go'}
info={'source_commit':sha,'flags':['-p','1','-trimpath','-buildvcs=false'],'sdk1272_sha256':'76812b213b1b2302c978d28fa52fa92d541704b9e7d9d5db8002c50e4018c4c5','builds':{}}
for v,go in compilers.items():
 env=dict(os.environ,GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOCACHE=str(t/('cache'+v)),GOMODCACHE=str(t/'modules'),TMPDIR=str(t/'runtime'))
 for k in ['GOFLAGS','GOEXPERIMENT','GODEBUG','GOGC','GOMEMLIMIT','GOMAXPROCS']:env.pop(k,None)
 (t/'runtime').mkdir(exist_ok=True)
 version=subprocess.check_output([go,'version'],env=env,text=True).strip();assert 'go1.'+('26.8' if v=='1268' else '27.2') in version
 started=time.monotonic();print('BUILD',v,version,flush=True)
 with (e/('build'+v+'.log')).open('w') as log:code=run_guarded([str(go),'build','-p','1','-trimpath','-buildvcs=false','-o',str(t/('bench'+v)),'./benchmarks/ownedprepared'],DiskGuard(w,12,12),cwd=r,env=env,output=log,timeout=1800)
 info['builds'][v]={'version':version,'seconds':time.monotonic()-started,'returncode':code}
 if code:(e/'builds.json').write_text(json.dumps(info,indent=2));sys.exit(code)
 info['builds'][v]['sha256']=hashlib.sha256((t/('bench'+v)).read_bytes()).hexdigest()
 info['builds'][v]['binary_bytes']=(t/('bench'+v)).stat().st_size
 info['builds'][v]['build_info']=subprocess.check_output([go,'version','-m',str(t/('bench'+v))],env=env,text=True).replace(str(t),'TEMP')
 (e/'builds.json').write_text(json.dumps(info,indent=2))
 print('BUILT',v,flush=True)
subprocess.run(['cc','-O2','-o',str(t/'process-cost'),str(r/'benchmarks/tools/process_cost.c')],check=True)
