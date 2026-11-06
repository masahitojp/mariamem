from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:])
runpy.run_path(str(s/'benchmarks/undorelay/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text())
r='internal/generatedgo/runtime_instance.go';p=s/r;op=Path(m['Replace'][str(p)]);v=op.read_text()
a='values = append(values, "MARIAMEM_GUEST_TIMING=1")';assert v.count(a)==1
v=v.replace(a,'values = append(values, "MARIAMEM_GUEST_TIMING=1", "MARIAMEM_INIT_DIAGNOSTICS=1")')
op.write_text(v)
for row in h:
 if row['path']==r:row['after_sha256']=hashlib.sha256(v.encode()).hexdigest()
(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
