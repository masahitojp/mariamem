from pathlib import Path
import sys,runpy,json,hashlib,re
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/undorelay'
runpy.run_path(str(s/'benchmarks/undoowner/overlay.py'),run_name='__main__')
maps=json.loads((o/'overlay.json').read_text());hashes=json.loads((o/'hashes.json').read_text());layout=json.loads((d/'layout.json').read_text())
def patch(rel,fn,edits):
 p=s/rel;old=p.read_text();assert hashlib.sha256(p.read_bytes()).hexdigest()==layout['new_generated_hashes'][rel]
 a=old.index('func Fn'+str(fn)+'(');b=old.index('\nfunc ',a+5);v=old[a:b]
 for before,after in edits:
  assert v.count(before)==1,(fn,before,v.count(before));v=v.replace(before,after)
 new=old[:a]+v+old[b:];out=o/('relay-'+p.name);out.write_text(new);maps['Replace'][str(p)]=str(out);hashes.append({'path':rel,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
patch('internal/generatedgo/code/p1/p1_pure.go',17010,[('L226:\n\t;\n\tFn16626(m, v889)','L226:\n\t;\n\tfunc(){defer base.URQueryRsegWait(m,v867)(); Fn16626(m,v889)}()')])
patch('internal/generatedgo/code/p2/p2_pure.go',17211,[
 ('func Fn17211(m *base.Module, l0 int32) int32 {','func Fn17211(m *base.Module, l0 int32) int32 {\n defer base.URPurgeExit(m)'),
 ('L18:\n\t;\n\tv82 =','L18:\n\t;\n base.URPurgeAcquire(m,v62)\n\tv82 ='),
 ('L303:\n\t;\n\tgoto L307','L303:\n\t;\n base.URPurgeRelease(m,v62,false)\n\tgoto L307'),
 ('L315:\n\t;\n\tgoto L308','L315:\n\t;\n base.URPurgeRelease(m,v62,true)\n\tgoto L308'),
 ('L316:\n\t;\n\tgoto L306','L316:\n\t;\n base.URPurgeEnd(m)\n\tgoto L306')])
for src,dst in [('trace.go.txt','update_notify.go'),('relay.go.txt','undo_relay.go'),('relay-test.go.txt','undo_relay_test.go')]:
 p=s/'internal/generatedgo/code/base'/dst;inp=d/src;maps['Replace'][str(p)]=str(inp);hashes[:]=[x for x in hashes if x['path']!=str(p.relative_to(s))];hashes.append({'path':str(p.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(maps,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
