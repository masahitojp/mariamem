"""Replay existing v0.4.6 cells; pair translator states, keep native anchors shared."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--binaries',type=Path,required=True)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[2];work=a.workspace.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard,run_guarded
image='mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
endpoint=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
env=dict(os.environ,DOCKER_HOST=endpoint,GOTOOLCHAIN='local')
env.pop('GOMAXPROCS',None)
roots={'v046':a.baseline.resolve(),'v047':root};bins=a.binaries.resolve();helper=bins/'process-cost'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
identity={'source_commits':{k:subprocess.check_output(['git','rev-parse','HEAD'],cwd=v,text=True).strip() for k,v in roots.items()},'image':image,'disk_guard_interval_seconds':5,'trials':3,'large_trials':1,'suite_count':4,'runtime_gomaxprocs':'Go default on same host','go':subprocess.check_output(['go','version'],text=True).strip(),'binary_sha256':{str(f.relative_to(bins)):sha(f) for f in sorted(bins.rglob('*')) if f.is_file()},'note':'Native anchors contain no translator and are run once per original cell, referenced by both states. New heap observations use identical harness bytes for both states. Historical v046 measurements are separate.','cells':[]}
(out/'inputs.json').write_text(json.dumps(identity,indent=2)+'\n')
def run(name,command,state='v047'):
 print('RUN',name,flush=True);t=time.monotonic()
 cellenv=dict(env,PYTHONPATH=str(roots[state]/'python'))
 guard=DiskGuard(work,20,24)
 with (out/(name+'.log')).open('w') as log:
  code=run_guarded(list(map(str,command)),guard,cwd=roots[state],env=cellenv,output=log,timeout=900,interval=5)
 record={'name':name,'returncode':code,'elapsed_seconds':time.monotonic()-t,'disk':guard.check()}
 identity['cells'].append(record);(out/'inputs.json').write_text(json.dumps(identity,indent=2)+'\n')
 if code:raise SystemExit(f'{name} failed: {code}')
 data=json.loads((out/(name+'.json')).read_text())
 if data.get('completed') is False:raise SystemExit(f'{name} incomplete')
 obs=data.get('go_resource_observation',{})
 if obs.get('process_peak_rss_bytes',0)>8*1024**3:raise SystemExit('Stop: completed cell exceeded 8GiB process RSS budget')
 print('PASS',name,flush=True)
for trial in range(3):
 cases=[('light',0,1,1),('fixture',10,8,1),('parallel',10,8,4)]
 if trial==0:cases.append(('large',100,8,1))
 for case,size,tables,workers in cases:
  for language in ('go','python'):
   for mode in ('fresh','fork'):
    for state in (('v046','v047') if (trial+(mode=='fork'))%2==0 else ('v047','v046')):
     name=f'{state}-{language}-{case}-{trial}-{mode}';dest=out/(name+'.json')
     if language=='go':
      command=[bins/state/'ownedprepared','-payload-mib',size,'-tables',tables,'-workers',workers,'-forks',4,'-workload','app-connections','-lifecycle',mode,'-go-resources','-helper',helper,'-label',identity['source_commits'][state],'-out',dest]
     else:
      command=[sys.executable,root/'benchmarks/python_product_suites.py','--payload-mib',size,'--tables',tables,'--workers',workers,'--count',4,'--mode',mode,'--host',bins/state/'mariamem-host','--image',image,'--helper',helper,'--out',dest]
     run(name,command,state)
  for mode in ('testcontainers','shared-reset'):
   name=f'anchor-python-{case}-{trial}-{mode}'
   run(name,[sys.executable,root/'benchmarks/python_product_suites.py','--payload-mib',size,'--tables',tables,'--workers',workers,'--count',4,'--mode',mode,'--host',bins/'v047/mariamem-host','--image',image,'--helper',helper,'--out',out/(name+'.json')])
 for mode in ('mariamem-fresh','mariamem-prepared','testcontainers-fresh','testcontainers-schema-reset'):
  states=('v046','v047') if mode.startswith('mariamem') else ('anchor',)
  for state in states:
   name=f'{state}-go-native-fixture-{trial}-{mode}';buildstate='v047' if state=='anchor' else state
   run(name,[bins/buildstate/'competitive','--suite-mode',mode,'--suite-count',4,'--image',image,'--json',out/(name+'.json')],buildstate)
print('PASS: original product cells completed; no performance conclusion implied')
