import json,os,subprocess,sys,time
from pathlib import Path
root=Path.cwd();w=root.parent;temp=w/'temp';out=w/'evidence/product';sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard,run_guarded
runtime=temp/'runtime';runtime.mkdir(exist_ok=True)
env=dict(os.environ,PYTHONPATH=str(root/'python'),TMPDIR=str(runtime),GOTOOLCHAIN='local',DOCKER_HOST=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip())
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
image='mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
for mode in ('fresh','fork'):
 name='go-large-0-'+mode
 cmd=[temp/'ownedprepared','-payload-mib','100','-forks','4','-workers','1','-tables','8','-workload','app-connections','-lifecycle',mode,'-label','5824ed1f205c84fc67574d6896afba412b57188b','-helper',temp/'process-cost','-out',out/(name+'.json')]
 print('RUN',name,flush=True)
 with (out/(name+'.log')).open('w') as log:code=run_guarded(list(map(str,cmd)),DiskGuard(w,8,12),cwd=root,env=env,output=log,timeout=900)
 print('DONE',name,code,flush=True)
 if code:sys.exit(code)
for mode in ('fresh','fork','testcontainers','shared-reset'):
 name='python-large-0-'+mode
 cmd=[temp/'venv/bin/python',root/'benchmarks/python_product_suites.py','--payload-mib','100','--tables','8','--count','4','--workers','1','--mode',mode,'--host',temp/'mariamem-host','--image',image,'--helper',temp/'process-cost','--out',out/(name+'.json')]
 print('RUN',name,flush=True)
 with (out/(name+'.log')).open('w') as log:code=run_guarded(list(map(str,cmd)),DiskGuard(w,8,12),cwd=root,env=env,output=log,timeout=900)
 print('DONE',name,code,flush=True)
 if code:sys.exit(code)
