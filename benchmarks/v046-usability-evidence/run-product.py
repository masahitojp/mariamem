import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path.cwd();workspace=root.parent;temp=workspace/'temp';evidence=workspace/'evidence';out=evidence/'product';out.mkdir(exist_ok=True)
sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard,run_guarded
from git_identity import require_commit
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();require_commit(root,sha)
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
image='mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
env=dict(os.environ,PYTHONPATH=str(root/'python'),GOTOOLCHAIN='local')
endpoint=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip();env['DOCKER_HOST']=endpoint
inputs={'source_commit':sha,'go':subprocess.check_output(['go','version'],text=True).strip(),'image':image,'docker_endpoint_kind':'unix socket','max_workers':4,'container_memory_limit':'768m (Python adapter)','disk_budget_gib':12,'minimum_free_gib':8,'trials':3,'benchmark_campaigns_concurrent':False,'binary_sha256':{n:hashlib.sha256((temp/n).read_bytes()).hexdigest() for n in ('mariamem-host','ownedprepared','competitive')},'host':{'uname':subprocess.check_output(['uname','-a'],text=True).strip(),'ram_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},'go_binary_source_commit':'5824ed1f205c84fc67574d6896afba412b57188b','steps':[]}
(evidence/'product-inputs.json').write_text(json.dumps(inputs,indent=2))
def run(name,command):
 existing=out/(name+'.json')
 if (name.startswith('go-') or name.startswith('pilot-go-')) and existing.exists():
  data=json.loads(existing.read_text())
  if data.get('completed',True):
   print('REUSE',name,flush=True)
   inputs['steps'].append({'name':name,'returncode':0,'reuse':True,'sha256':hashlib.sha256(existing.read_bytes()).hexdigest()})
   return
 print('RUN',name,flush=True);started=time.monotonic()
 with (out/(name+'.log')).open('w') as log:
  code=run_guarded(list(map(str,command)),DiskGuard(workspace,8,12),cwd=root,env=env,output=log,timeout=900)
 inputs['steps'].append({'name':name,'returncode':code,'seconds':time.monotonic()-started})
 (evidence/'product-inputs.json').write_text(json.dumps(inputs,indent=2))
 print('DONE',name,code,flush=True)
 if code:raise SystemExit(code)
# Small pilots prove adapters/oracles before collecting comparable suite cells.
for mode in ('mariamem-fresh','mariamem-prepared','testcontainers-fresh','testcontainers-schema-reset'):
 n='pilot-go-'+mode
 run(n,[temp/'competitive','--suite-mode',mode,'--suite-count','1','--image',image,'--json',out/(n+'.json')])
for mode in ('fresh','fork','testcontainers','shared-reset'):
 n='pilot-python-'+mode
 run(n,[temp/'venv/bin/python',root/'benchmarks/python_product_suites.py','--mode',mode,'--count','1','--host',temp/'mariamem-host','--image',image,'--helper',temp/'process-cost','--out',out/(n+'.json')])
for trial in range(3):
 for case,size,tables,workers in [('light',0,1,1),('fixture',10,8,1),('parallel',10,8,4)]:
  for mode in ('fresh','fork') if trial%2==0 else ('fork','fresh'):
   n=f'go-{case}-{trial}-{mode}'
   run(n,[temp/'ownedprepared','-lifecycle',mode,'-payload-mib',str(size),'-tables',str(tables),'-workers',str(workers),'-forks','4','-workload','app-connections','-helper',temp/'process-cost','-label','5824ed1f205c84fc67574d6896afba412b57188b','-out',out/(n+'.json')])
  modes=('fresh','fork','testcontainers','shared-reset');modes=modes[trial:]+modes[:trial]
  for mode in modes:
   n=f'python-{case}-{trial}-{mode}'
   run(n,[temp/'venv/bin/python',root/'benchmarks/python_product_suites.py','--mode',mode,'--payload-mib',str(size),'--tables',str(tables),'--workers',str(workers),'--count','4','--host',temp/'mariamem-host','--image',image,'--helper',temp/'process-cost','--out',out/(n+'.json')])
 for mode in ('mariamem-fresh','mariamem-prepared','testcontainers-fresh','testcontainers-schema-reset'):
  n=f'go-native-fixture-{trial}-{mode}'
  run(n,[temp/'competitive','--suite-mode',mode,'--suite-count','4','--image',image,'--json',out/(n+'.json')])
