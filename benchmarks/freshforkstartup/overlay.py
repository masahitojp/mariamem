from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:])
runpy.run_path(str(s/'benchmarks/staticimagestages/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());rel='internal/generatedgo/runtime_instance.go';p=Path(m['Replace'][str(s/rel)]);old=p.read_text()
a='values = append(values, "MARIAMEM_GUEST_TIMING=1")';assert old.count(a)==1
new=old.replace(a,'values = append(values, "MARIAMEM_GUEST_TIMING=1", "MARIAMEM_INIT_DIAGNOSTICS=1")');p.write_text(new)
h.append({'path':rel,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
