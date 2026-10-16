import hashlib,itertools,json,os,platform,subprocess,sys,tempfile
from pathlib import Path
h=Path(__file__).resolve().parent;root=h.parents[2];w=root.parent;t=w/'temp';e=w/'evidence';python=t/'venv/bin/python'
stage=sys.argv[1];out=e/stage;out.mkdir()
record=json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=root));record.update(platform=platform.platform(),machine=platform.machine(),binaries={n:hashlib.sha256((t/n).read_bytes()).hexdigest() for n in ['mariamem-host','broker']},harness={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in h.glob('*.py')})
(out/'inputs.json').write_text(json.dumps(record,indent=2)+'\n')
def run(mode,rows,repeat):
 label=f'n{rows}-r{repeat}-{mode}';case=out/label;case.mkdir();scratch=Path(tempfile.mkdtemp(prefix=stage+'-'+label+'-',dir=t));env=os.environ.copy();env.update(TMPDIR=str(scratch),PYTHONPYCACHEPREFIX=str(t/'pycache'))
 for key in ['MARIAMEM_HEAP','MARIAMEM_HEAP_KIND','MARIAMEM_HEAP_FAULT','MARIAMEM_HEAP_AUDIT','MARIAMEM_SPIKE_METRICS']:env.pop(key,None)
 if stage=='resources':
  metrics=case/'metrics';metrics.mkdir();env['MARIAMEM_SPIKE_METRICS']=str(metrics)
 cmd=[str(python),str(h/'workflow.py'),'--mode',mode,'--host',str(t/'mariamem-host'),'--broker',str(t/'broker'),'--rows',str(rows),'--output',str(case/'result.json')]
 if stage=='resources':cmd.append('--resources')
 with (case/'output.txt').open('w') as f:subprocess.run(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=150)
 r=json.loads((case/'result.json').read_text());assert not list(scratch.iterdir()),scratch;scratch.rmdir();print(stage,label,r['status'],round(r['whole_ms'],2),flush=True)
if stage=='pilot':
 for mode in ['control','file','heap']:run(mode,100,-1)
elif stage in ['plain','resources']:
 orders=list(itertools.permutations(['control','file','heap'])) if stage=='plain' else [('control','file','heap'),('file','heap','control'),('heap','control','file')]
 for rows in [100,10000]:
  for rep,modes in enumerate(orders):
   for mode in modes:run(mode,rows,rep)
else:raise ValueError(stage)
