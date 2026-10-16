import json,os,subprocess,tempfile
from pathlib import Path
h=Path(__file__).resolve().parent;root=h.parents[2];w=root.parent;t=w/'temp';e=w/'evidence';out=e/'verify';out.mkdir();python=t/'venv/bin/python'
for name,cmd in [('boundaries',[str(python),str(h/'boundaries.py'),'--broker',str(t/'broker'),'--output',str(out/'boundaries.json')]),('fixture',[str(python),'-m','pytest','-q','-p','no:cacheprovider',str(h/'test_fixture.py')]),('audit',[str(python),str(h/'workflow.py'),'--mode','heap','--host',str(t/'mariamem-host'),'--broker',str(t/'broker'),'--output',str(out/'audit.json')])]:
 scratch=Path(tempfile.mkdtemp(prefix='verify-'+name+'-',dir=t));env=os.environ.copy();env.update(TMPDIR=str(scratch),PYTHONPYCACHEPREFIX=str(t/'pycache'),SPIKE_BROKER=str(t/'broker'),PYTHONPATH=str(h))
 for k in ['MARIAMEM_HEAP','MARIAMEM_HEAP_FAULT','MARIAMEM_HEAP_AUDIT','MARIAMEM_SPIKE_METRICS']:env.pop(k,None)
 if name=='audit':env['MARIAMEM_HEAP_AUDIT']='1'
 with (out/(name+'.txt')).open('w') as f:subprocess.run(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 assert not list(scratch.iterdir()),scratch;scratch.rmdir();print(name,'PASS',flush=True)
