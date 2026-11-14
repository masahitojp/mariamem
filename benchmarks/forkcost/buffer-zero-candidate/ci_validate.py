"""Run the candidate-specific actual guest controls on canonical CI source.

Test-only overlays inject EIO and observe real redo recovery. They never enter
product code or performance binaries. Output is an external disposable directory.
"""
from pathlib import Path
import argparse,os,subprocess,shutil,json,sys
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();root=a.root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);e=out/'evidence';t=out/'temp';e.mkdir();t.mkdir();(t/'tmp').mkdir()
# The generic overlay builder is the same recipe used locally. Its explicit
# canonical root replaces only the local workspace path, without editing source.
s=(HERE/'tools/build-extra.py').read_text();old="product=X/'worktree' if variant=='baseline' else T/'native/product'";assert old in s;s=s.replace(old,'product=Path(os.environ["MARIAMEM_BUFFER_CANDIDATE_ROOT"])').replace("GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),",'');(e/'build-extra.py').write_text(s)
for n in ('correct','fault','recovery'):
 shutil.copytree(HERE/'harness'/n,t/n)
 p=t/n/'go.mod';v=p.read_text();p.write_text(v[:v.index('replace github.com/masahitojp/mariamem')]+f'replace github.com/masahitojp/mariamem => {root}\n')
for n in ('buffer_fault_experiment.go','buffer_recovery_witness.go'):shutil.copy2(HERE/'harness'/(n+'.txt'),t/n)
env=dict(os.environ,MARIAMEM_BUFFER_CANDIDATE_ROOT=str(root),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'tmp'))
def run(name,cmd):
 with (e/(name+'.log')).open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print('PASS',name,flush=True)
run('build',[sys.executable,str(e/'build-extra.py'),'candidate'])
for name,binary,args in [('basic','correct',['-case','basic']),('large','correct',['-case','large']),('fault','fault',[]),('recovery-clean','recovery',['-crash=false']),('recovery-dirty','recovery',['-crash=true'])]:
 run(name,[str(t/('candidate-'+binary)),*args,'-out',str(e/(name+'.json'))]);assert json.loads((e/(name+'.json')).read_text())['success']
(e/'result.json').write_text(json.dumps({'result':'PASS','guest_sha256':json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256'],'scope':'canonical actual basic/large/compressed/resize/Fork/fault/clean-vs-dirty redo controls; test-only overlays excluded from product'},indent=2)+'\n')
