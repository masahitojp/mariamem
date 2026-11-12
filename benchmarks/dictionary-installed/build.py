"""Build identical fixed-comparison harnesses against committed installed runtimes."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, tarfile, time

S = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--work-dir', type=Path, required=True)
p.add_argument('--candidate', required=True)
a = p.parse_args()
W = a.work_dir.resolve(); T = W/'temp'; E = W/'evidence'
T.mkdir(parents=True); E.mkdir()
BASE = '8df45792a927e440972266ee799d6f7223713e14'
HARNESS = 'd24087eedd21c6384c231fb119c8e98da7b370aa'
INSTRUMENT = 'e556c36570e1be023f8a9c8243381c6605079592:benchmarks/uca-p8-attribution/reproduction/instrument.py'
def git(*args): return subprocess.check_output(['git', *args], cwd=S, text=True).strip()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory(path): return {str(f.relative_to(path)): sha(f) for f in sorted(path.rglob('*')) if f.is_file()}
def dump(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
assert not git('status', '--porcelain')
identities = {key: json.loads(subprocess.check_output([sys.executable, 'scripts/git_identity.py', 'inspect', ref], cwd=S, text=True)) for key, ref in {'baseline': BASE, 'candidate': a.candidate, 'harness': HARNESS, 'execution': 'HEAD'}.items()}
assert all(value['object_type']=='commit' for value in identities.values())
dump(E/'sources.json', identities)
env = {k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','GIT_'))}
cache = W.parent/'temp'
env.update(GOCACHE=str(cache/'gocache'), GOPATH=str(cache/'gopath'), GOMODCACHE=str(cache/'modcache'), GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='', GOMAXPROCS='2', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(T/'scratch'), GOTMPDIR=str(T/'scratch'))
(T/'scratch').mkdir()
def archive(ref, paths, dest):
    path=T/'source.tar'
    with path.open('wb') as out: subprocess.run(['git','archive',ref,*paths],cwd=S,stdout=out,check=True)
    with tarfile.open(path) as source: source.extractall(dest,filter='data')
    path.unlink()
inject=T/'instrument.py'
inject.write_bytes(subprocess.check_output(['git','show',INSTRUMENT],cwd=S))
for arm in ('baseline','candidate'):
    root=T/arm; root.mkdir()
    archive(identities[arm]['source_commit'],[],root)
    archive(HARNESS,['tests/timer_calibration/runner'],root)
    runner=root/'tests/timer_calibration/runner'
    runtime=inventory(root/'internal/generatedgo')
    guest=json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
    for mode in ('off','phases'):
        if mode=='phases': subprocess.run([sys.executable,inject,S,runner],check=True,env=env)
        before=inventory(runner); binary=T/(arm+'-'+mode+'.test'); start=time.monotonic()
        with (T/(arm+'-'+mode+'-build.log')).open('w') as out:
            subprocess.run(['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-c','-o',binary,'./maria/store'],cwd=runner,env=env,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=1200)
        assert runtime==inventory(root/'internal/generatedgo')
        dump(E/(arm+'-'+mode+'-runner.json'),{'source':identities[arm],'execution_source':identities['execution'],'harness':identities['harness'],'harness_files_sha256':before,'runtime_inventory_sha256':hashlib.sha256(json.dumps(runtime,sort_keys=True).encode()).hexdigest(),'binary_sha256':sha(binary),'compile_seconds':time.monotonic()-start,'guest_sha256':guest,'buildinfo':subprocess.check_output(['go','version','-m',binary],env=env,text=True).replace(str(W),'<WORK>')})
        print(arm,mode,'BUILD PASS',round(time.monotonic()-start,1),flush=True)
for mode in ('off','phases'):
    assert json.loads((E/('baseline-'+mode+'-runner.json')).read_text())['harness_files_sha256']==json.loads((E/('candidate-'+mode+'-runner.json')).read_text())['harness_files_sha256']
print('FOUR RUNNERS READY; measurement not started',flush=True)
