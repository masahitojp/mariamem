from pathlib import Path
import subprocess,os
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';(T/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
for label,cwd,args in [('unit',W/'worktree',['go','test','-c','-vet=off','-p','1','-overlay',str(E/'overlay.json'),'-o',str(T/'unit'),'./internal/guest']),('suite',T/'maria',['go','test','-c','-vet=off','-p','1','-overlay',str(E/'overlay.json'),'-o',str(T/'probe'),'./store'])]:
 with (E/(label+'-build.txt')).open('w')as f:subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=1200)
 print('BUILT',label,flush=True)
for arm in [0,1]:
 with (E/f'unit-arm{arm}.txt').open('w')as f:subprocess.run([str(T/'unit'),'-test.v','-test.timeout=120s'],env=dict(env,MARIAMEM_EXPERIMENT_READ_BUFFER=str(arm)),stdout=f,stderr=f,check=True,timeout=150)
 print('UNIT PASS',arm,flush=True)
