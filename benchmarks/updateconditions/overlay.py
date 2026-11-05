from pathlib import Path
import sys,runpy,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);o.mkdir(parents=True,exist_ok=True);maps={'Replace':{}};hashes=[]
p=s/'internal/generatedgo/code/p5/p5_pure.go';old=p.read_text();needle='v107 = Fn5739(m, int32(25), v8)';assert old.count(needle)==1;v=old.replace(needle,'loadArgc, loadArgv, restoreLoadStack := base.BufLoadArg(m,v8)\n v107 = Fn5739(m, loadArgc, loadArgv)\n restoreLoadStack()');target=o/'p5_pure.go';target.write_text(v);maps['Replace'][str(p)]=str(target);hashes.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
for name,relative in [('argv.go.txt','buffer_load.go'),('argv-test.go.txt','buffer_load_test.go')]:
 source=s/'benchmarks/bufferflush'/name;maps['Replace'][str(s/'internal/generatedgo/code/base'/relative)]=str(source);hashes.append({'path':'internal/generatedgo/code/base/'+relative,'before_sha256':None,'after_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(maps,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
