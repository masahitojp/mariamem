from pathlib import Path
import os,sys,json,hashlib,subprocess,shutil
W=Path(__file__).resolve().parents[1];arm=sys.argv[1];A=W if arm=='candidate' else W.parent/'timer-measure-baseline';T=A/'temp';P=T/'runtime/product';S=W/'worktree'
receipt=json.loads((T/'runtime/development.json').read_text())
assert receipt['smoke']=='PASS'
source=S/'tests/timer_calibration/runner';target=P/'tests/timer_calibration/runner'
def inventory(p):return {str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob('*')) if f.is_file()}
if not target.exists(): shutil.copytree(source,target)
assert inventory(source)==inventory(target)
expected=receipt['generated_inventory'];assert inventory(P/'internal/generatedgo')==expected
runtime_hash=hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()
env=dict(os.environ,GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
binary=T/'shop.test'
with (T/'runner-build.log').open('w') as f:
 result=subprocess.run(['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-c','-o',str(binary),'./maria/store'],cwd=target,env=env,stdout=f,stderr=subprocess.STDOUT)
if result.returncode:print((T/'runner-build.log').read_text()[-5000:]);sys.exit(result.returncode)
assert inventory(P/'internal/generatedgo')==expected
out={'arm':arm,'host_source_commit':receipt['host_source_identity']['commit'],'guest_source_commit':receipt['source_identity']['commit'],'guest_sha256':receipt['guest_sha256'],'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'harness_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip(),'harness_files_sha256':inventory(source),'generated_inventory_sha256':runtime_hash,'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True).replace(str(A),'<WORKSPACE>')}
(W/'evidence'/(arm+'-runner.json')).write_text(json.dumps(out,indent=2)+'\n');print(arm,'runner build PASS',out['binary_sha256'])
