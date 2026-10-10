import os,sys,json,subprocess
from pathlib import Path
r=Path.cwd();w=r.parent;t=w/'temp';e=w/'evidence';sys.path.insert(0,str(r/'scripts'))
from experiment_disk import DiskGuard,run_guarded
source=json.loads((e/'builds.json').read_text())['source_commit']
env=dict(os.environ,GOTOOLCHAIN='local',GOMAXPROCS='8',GOGC='100',GOMEMLIMIT='off',GODEBUG='',TMPDIR=str(t/'runtime'))
env.pop('GOEXPERIMENT',None)
for v in ['1268','1272']:
 go=Path(os.environ['GO1268_BIN']) if v=='1268' else t/'sdk1272/go/bin/go'
 for mode in ['fresh','fork']:
  name='profile-'+v+'-'+mode
  cmd=[t/('bench'+v),'-payload-mib','10','-tables','8','-workers','1','-forks','20','-lifecycle',mode,'-workload','app-connections','-toolchain-metrics','-label',source,'-out',e/(name+'.json'),'-cpu-profile',e/(name+'-cpu.pprof'),'-alloc-profile',e/(name+'-alloc.pprof')]
  with (e/(name+'.log')).open('w') as log:code=run_guarded(list(map(str,cmd)),DiskGuard(w,12,12),cwd=r,env=env,output=log,timeout=240)
  if code:sys.exit(code)
  for kind in ['cpu','alloc']:
   command=[go,'tool','pprof','-top','-nodecount=25']
   if kind=='alloc':command.append('-alloc_space')
   command.extend([t/('bench'+v),e/(name+'-'+kind+'.pprof')])
   result=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=env,check=True)
   (e/(name+'-'+kind+'-top.txt')).write_text(result.stdout)
  print('PROFILE',v,mode,flush=True)
