from pathlib import Path
import subprocess,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);b=s/'benchmarks/lexercandidate'
subprocess.run([sys.executable,str(s/'benchmarks/lexerprepared/overlay.py'),str(s),str(o),'--undo'],check=True)
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text())
def put(rel,v):
 p=s/rel;d=o/('lc-'+rel.replace('/','_'));d.write_text(v);m['Replace'][str(p)]=str(d)
 h[:]=[x for x in h if x['path']!=rel];h.append({'path':rel,'before_sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
r='internal/generatedgo/runtime_instance.go';v=Path(m['Replace'][str(s/r)]).read_text();a='values = append(values, "MARIAMEM_GUEST_TIMING=1")';assert v.count(a)==1;put(r,v.replace(a,'values = append(values, "MARIAMEM_GUEST_TIMING=1", "MARIAMEM_INIT_DIAGNOSTICS=1")'))
r='internal/generatedgo/code/base/lexer_prepared.go';v=Path(m['Replace'][str(s/r)]).read_text();a='int32)int32{\n if lpMode';assert v.count(a)==1;put(r,v.replace(a,'int32)int32{\n LCExport(m,cs)\n if lpMode'))
r='internal/generatedgo/code/base/lexer_prepared.go';v=Path(m['Replace'][str(s/r)]).read_text()
a='b,ok:=lpBindings[uint32(cs)]\n if !ok||lpU32(m,uint32(cs))!=b.number||lpU32(m,uint32(cs)+12)&1==0{';assert v.count(a)==1
v=v.replace(a,'b,ok:=lcByNumber[lpU32(m,uint32(cs))]\n if !ok||lpU32(m,uint32(cs)+12)&1==0{')
a='lpPut(m,uint32(clone)+72,0);lpPut(m,uint32(clone)+76,0)';assert v.count(a)==1
v=v.replace(a,a+';lpPut(m,uint32(clone)+12,0)')
put(r,v)
r='internal/generatedgo/code/base/lexer_prepared_test.go';v=Path(m['Replace'][str(s/r)]).read_text();v=v.replace('lpPut(m,cs,b.number+4096)','lpPut(m,cs,65535)');put(r,v)
put('internal/generatedgo/code/base/lexer_export.go',(b/'export.go.txt').read_text())
put('internal/generatedgo/code/base/lexer_export_test.go',(b/'export_test.go.txt').read_text())
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
