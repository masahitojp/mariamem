"""Fresh-process paired workflows; do not mix resource and plain observations."""
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent;root=here.parents[2];w=root.parent;e=w/'evidence';t=w/'temp'
stage=sys.argv[1];out=e/stage;out.mkdir()
identity=json.loads(subprocess.check_output(['python3',str(root/'scripts/git_identity.py'),'inspect','HEAD'],cwd=root))
identity.update(platform=platform.platform(),machine=platform.machine(),binary_sha256=hashlib.sha256((t/'heap-spike').read_bytes()).hexdigest(),runner_sha256=hashlib.sha256((here/'runner/main.go').read_bytes()).hexdigest())
(out/'inputs.json').write_text(json.dumps(identity,indent=2)+'\n')
def run(mode,rows,repeat,flags=()):
 label=f'n{rows}-r{repeat}-{mode}';scratch=Path(__import__('tempfile').mkdtemp(prefix=stage+'-'+label+'-',dir=t));env=os.environ.copy();env['TMPDIR']=str(scratch)
 cmd=[str(t/'heap-spike'),'--mode',mode,'--rows',str(rows),'--output',str(out/(label+'.json')),*flags]
 with (out/(label+'.txt')).open('w') as log:subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 result=json.loads((out/(label+'.json')).read_text());print(stage,label,result['status'],round(result.get('whole_ms',0),2),flush=True)
 assert not list(scratch.iterdir()),scratch
if stage in ['verify','measure','final']:
 for child in (['audit','boundaries'] if stage=='verify' else (['plain','resources'] if stage=='measure' else ['pilot','verify','measure'])):subprocess.run([sys.executable,__file__,child],check=True)
elif stage=='pilot':
 for mode in ['control','heap']:run(mode,100,-1)
elif stage=='audit':run('heap',100,0,['--audit'])
elif stage=='boundaries':run('heap',100,0,['--boundaries'])
elif stage in ['plain','resources']:
 for rows in [100,10000]:
  for repeat in range(5 if stage=='plain' else 3):
   modes=['control','heap'];modes=modes[repeat%2:]+modes[:repeat%2]
   for mode in modes:run(mode,rows,repeat,[] if stage=='plain' else ['--resources'])
else:raise ValueError(stage)
