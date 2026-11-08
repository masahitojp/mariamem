from pathlib import Path
import sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);o.mkdir(exist_ok=True,parents=True)
p=s/'internal/generatedgo/code/p5/p5_pure.go';old=p.read_text();needle='v107 = Fn5739(m, int32(25), v8)';assert old.count(needle)==1
new=old.replace(needle,'v107 = Fn5739(m, base.PoolArgv(m, int32(25), v8), v8)');target=o/'p5_pure.go';target.write_text(new)
sel=s/'benchmarks/issue88poolab/selector.go.txt'
replace={str(p):str(target),str(s/'internal/generatedgo/code/base/pool_selector.go'):str(sel),str(s/'internal/generatedgo/code/base/pool_selector_test.go'):str(s/'benchmarks/issue88poolab/selector_test.go.txt')}
(o/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
(o/'hashes.json').write_text(json.dumps({'generated_path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'selector_sha256':hashlib.sha256(sel.read_bytes()).hexdigest()},indent=2)+'\n')
