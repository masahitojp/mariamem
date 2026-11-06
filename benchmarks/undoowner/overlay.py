from pathlib import Path
import sys,runpy,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:])
runpy.run_path(str(s/'benchmarks/updatenotify/overlay.py'),run_name='__main__')
maps=json.loads((o/'overlay.json').read_text());hashes=json.loads((o/'hashes.json').read_text());d=s/'benchmarks/undoowner'
p=s/'internal/generatedgo/code/p3/p3_pure.go';old=p.read_text();layout=json.loads((d/'layout.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==layout['generated_p3_sha256']
needle='L272:\n\t;\n\tFn16621(m, v985)';assert old.count(needle)==1
new=old.replace(needle,'L272:\n\t;\n\tfunc(){defer base.UWOwnerBegin(m,v899)(); Fn16621(m,v985)}()')
out=o/'owner-p3_pure.go';out.write_text(new);maps['Replace'][str(p)]=str(out);hashes.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
for src,dst in [('trace.go.txt','update_notify.go'),('owner.go.txt','undo_owner.go'),('owner-test.go.txt','undo_owner_test.go')]:
 p=s/'internal/generatedgo/code/base'/dst;inp=d/src;maps['Replace'][str(p)]=str(inp);hashes[:]=[x for x in hashes if x['path']!=str(p.relative_to(s))];hashes.append({'path':str(p.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(maps,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
