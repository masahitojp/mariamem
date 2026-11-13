from pathlib import Path
import subprocess,os
E=Path(__file__).resolve().parent
for p in (1,8):
 files=sorted((E/'runs').glob(f'profile-p{p}.json-wave*.pprof'))
 for name,args in [('top',['-top','-nodecount=35']),('memclr',['-tree','-focus=memclr','-nodecount=35']),('grow',['-tree','-focus=Grow|Mprotect|Mmap','-nodecount=35'])]:
  r=subprocess.run(['go','tool','pprof',*args,*map(str,files)],capture_output=True,text=True,check=True)
  text=r.stdout.replace(str(E.parent),'<workspace>').replace('/Users/masahito/','<home>/')
  (E/f'profile-p{p}-{name}.txt').write_text(text)
  if name=='top':print(p,text)
