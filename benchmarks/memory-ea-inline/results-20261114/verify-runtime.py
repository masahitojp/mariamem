from pathlib import Path
import os,subprocess
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';S=W/'worktree';env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
for label in ['baseline','candidate']:
 with(E/(label+'-generatedmemory.txt')).open('w')as f:subprocess.run(['go','test','-v','-count=1','-vet=off','-p','1','-tags=integration','-overlay',str(E/(label+'-overlay.json')),'./tests/generatedmemory','-timeout=3m'],cwd=S,env=env,stdout=f,stderr=f,check=True,timeout=300)
 print('GENERATED MEMORY PASS',label,flush=True)
