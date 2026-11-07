from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/innodbopenspan'
runpy.run_path(str(s/'benchmarks/freshforkstartup/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());layout=json.loads((d/'layout.json').read_text())
def patch(rel,before,after):
 p=s/rel;inp=Path(m['Replace'].get(str(p),p));old=inp.read_text();assert old.count(before)==1,(rel,before)
 v=old.replace(before,after);out=o/('openspan-'+p.name);out.write_text(v);m['Replace'][str(p)]=str(out);h.append({'path':rel,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
p=s/'internal/generatedgo/code/p0/p0_pure.go';assert hashlib.sha256(p.read_bytes()).hexdigest()==layout['p0_sha256']
assert hashlib.sha256((s/'internal/generatedgo/code/p2/p2_pure.go').read_bytes()).hexdigest()==layout['p2_sha256']
needle='v11116 = Fn16690(m, int32(26778912), int32(0), v11097, v11085+int32(792))'
patch(str(p.relative_to(s)),needle,'v11116 = func()int32{defer base.OpenSpanEnter(m,int32(26778912),int32(0),v11097)();return Fn16690(m,int32(26778912),int32(0),v11097,v11085+int32(792))}()')
patch('internal/generatedgo/runtime_instance.go','base.UWBind(m,diagChild,diagOK)','base.UWBind(m,diagChild,diagOK)\n base.OpenSpanBind(m,ctx,diagOK)\n defer base.OpenSpanUnbind(m)')
for src,dst in [('span.go.txt','open_span.go'),('span-test.go.txt','open_span_test.go')]:
 inp=d/src;target=s/'internal/generatedgo/code/base'/dst;m['Replace'][str(target)]=str(inp);h.append({'path':str(target.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
