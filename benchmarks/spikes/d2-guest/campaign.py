"""Run one bounded campaign stage in isolated scratch; outer disk guard required."""
import os,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent;root=here.parents[2];w=root.parent;t=w/'temp';e=w/'evidence'
stage=sys.argv[1]
if stage=='measure':
 for child in ('boundaries-e','plain','resources'):
  subprocess.run([sys.executable,__file__,child],check=True)
 sys.exit(0)
scratch=t/('scratch-'+stage);scratch.mkdir(exist_ok=True)
env=os.environ.copy();env['TMPDIR']=str(scratch)
python=t/'venv/bin/python';common=['--host',str(t/'d2-host'),'--output',str(e/stage)]
if stage.startswith('boundaries-'):
 cmd=[str(python),str(here/'boundaries.py'),'--mode',stage.split('-')[1]]+common
else:
 cmd=[str(python),str(here/'run.py')]+common
 if stage in ('pilot','audit'):cmd+=['--'+stage]
 elif stage=='plain':cmd+=['--repeats','5']
 elif stage=='resources':cmd+=['--resources','--repeats','3']
 else:raise ValueError(stage)
with (e/(stage+'.txt')).open('w') as log:
 subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print(stage,'PASS',flush=True)
