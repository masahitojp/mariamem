from pathlib import Path
import subprocess,os,json,hashlib,sys
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';variant=sys.argv[1];product=X/'worktree' if variant=='baseline' else T/'native/product'
env=dict(os.environ,GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
records={}
for name in ['probe','suite','lifecycle','correct']:
 H=T/name;mod=(H/'go.mod').read_text();mod=mod[:mod.index('replace github.com/masahitojp/mariamem')]+f'replace github.com/masahitojp/mariamem => {product}\n';(H/'go.mod').write_text(mod)
 cmd=['go','build' if name!='suite' else 'test','-p','1','-trimpath','-buildvcs=false']
 if name=='suite':cmd+=['-c']
 out=T/f'{variant}-{name}';cmd+=['-o',str(out),'.' if name!='suite' else './store']
 print('building',variant,name,flush=True);subprocess.run(cmd,cwd=H,env=env,check=True,timeout=1800)
 records[name]=dict(sha256=hashlib.sha256(out.read_bytes()).hexdigest(),argv=cmd)
(E/f'{variant}-binaries.json').write_text(json.dumps(records,indent=2)+'\n')
