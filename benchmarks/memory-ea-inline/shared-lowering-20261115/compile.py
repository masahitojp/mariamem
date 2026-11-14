from pathlib import Path
import subprocess,os,json
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence';env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8')
for label in ['candidate']:
 for pkg,fn in [('p3','Fn13460'),('p1','Fn15594')]:
  extra=['-overlay',str(E/'overlay.json')]if label=='candidate'else[]
  with(E/(label+'-'+pkg+'-build.log')).open('w')as f:subprocess.run(['go','build','-p','1',*extra,'-o',str(T/(label+'-'+pkg+'.a')),'./internal/generatedgo/code/'+pkg],cwd=S,env=env,stdout=f,stderr=f,check=True,timeout=1200)
  with(E/(label+'-'+fn+'-assembly.txt')).open('w')as f:subprocess.run(['go','tool','objdump','-s',fn+'$',str(T/(label+'-'+pkg+'.a'))],cwd=S,env=env,stdout=f,stderr=f,check=True,timeout=120)
  print(label,pkg,'PASS',flush=True)
