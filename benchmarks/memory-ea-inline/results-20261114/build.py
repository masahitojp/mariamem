from pathlib import Path
import os,subprocess,json,hashlib,time
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';S=W/'worktree';(T/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
for label in ['baseline','candidate']:
 over=str(E/(label+'-overlay.json'))
 with(E/(label+'-focused.txt')).open('w')as f:subprocess.run(['go','test','-v','-count=1','-vet=off','-p','1','-overlay',over,'./internal/generatedgo/code/base','-run','TestExperiment|TestBulkBoundsAndEffects|TestHostImportLogicalMemory|TestPreparedGrowthOwnershipAndZeroFill|TestNarrow|TestOwnedPrivateViewsGrowthAndRelease'],cwd=S,env=env,stdout=f,stderr=f,check=True,timeout=180)
 print('FOCUSED PASS',label,flush=True)
 with(E/(label+'-build.txt')).open('w')as f:subprocess.run(['go','test','-c','-vet=off','-p','1','-overlay',over,'-gcflags=github.com/masahitojp/mariamem/internal/generatedgo/code/base=-m=2','-o',str(T/(label+'.test')),'./store'],cwd=T/'maria',env=env,stdout=f,stderr=f,check=True,timeout=1200)
 print('BUILT',label,flush=True)
(E/'binary-hashes.json').write_text(json.dumps({l:{'sha256':hashlib.sha256((T/(l+'.test')).read_bytes()).hexdigest(),'bytes':(T/(l+'.test')).stat().st_size}for l in ['baseline','candidate']},indent=2))
