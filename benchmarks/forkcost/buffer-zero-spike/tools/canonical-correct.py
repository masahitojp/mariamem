from pathlib import Path
import os,subprocess
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';H=T/'correct';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),MARIAMEM_BP_ZERO_MODE_INTERNAL='baseline')
p=H/'go.mod';s=p.read_text();p.write_text(s.replace('../native/product','../../worktree'))
try:subprocess.run(['go','build','-p','1','-trimpath','-overlay',str(T/'canonical-overlay.json'),'-o',str(T/'canonical-correct'),'.'],cwd=H,env=env,check=True)
finally:p.write_text(s)
for case in ['basic','large']:
 with (E/f'canonical-{case}.log').open('w') as f:subprocess.run([str(T/'canonical-correct'),'-case',case,'-out',str(E/f'canonical-{case}.json')],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=950,check=True)
 print('PASS canonical',case,flush=True)
