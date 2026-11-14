from pathlib import Path
import subprocess,os,json,hashlib,sys
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
variant=sys.argv[1];product=X/'worktree' if variant=='canonical' else T/'native/product';bins={}
for name in ['probe','suite']:
 H=T/name;mod=(H/'go.mod').read_text();mod=mod[:mod.index('replace github.com/masahitojp/mariamem')]+f'replace github.com/masahitojp/mariamem => {product}\n';(H/'go.mod').write_text(mod)
 cmd=['go','build' if name=='probe' else 'test','-p','1','-trimpath','-buildvcs=false']
 if name=='suite':cmd+=['-c']
 if variant=='canonical':cmd+=['-overlay',str(T/'canonical-overlay.json')]
 out=T/f'{variant}-{name}';cmd+=['-o',str(out),'.' if name=='probe' else './store']
 print('building',variant,name,flush=True);subprocess.run(cmd,cwd=H,env=env,check=True);bins[name]=hashlib.sha256(out.read_bytes()).hexdigest()
(E/f'{variant}-binaries.json').write_text(json.dumps(bins,indent=2)+'\n')
