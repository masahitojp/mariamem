"""Focused adapter test bundle; production tests pin a different guest's Fn ABI."""
import os,sys,subprocess,json
from pathlib import Path
w=Path('.').resolve();r=w/'worktree';sys.path.insert(0,str(r/'scripts'));from build_feedback import go_environment
os.environ['MARIAMEM_DEV_WORKSPACE']=str(w);env=go_environment({k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')});env.update(GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOWORK='off',GOENV='off',GOMAXPROCS='2',GOGC='50')
product=w/'temp/host/product';runtime=product/'internal/generatedgo'
package=json.loads(subprocess.check_output(['go','list','-json','./internal/generatedgo'],cwd=product,env=env,text=True));files=['internal/generatedgo/'+name for name in package['GoFiles']]+['internal/generatedgo/runtime_capture_test.go']
cmd=['go','test','-trimpath','-p','1','-buildvcs=false','-v','-run','^TestWireCaptureWaitsForFailedWorkerPeer$','-timeout','30s',*files];print(json.dumps({'command':cmd,'excluded':'production index-bound tests are outside this focused command; new guest broad-package qualification is not claimed'},indent=2),flush=True);subprocess.run(cmd,cwd=product,env=env,check=True)
