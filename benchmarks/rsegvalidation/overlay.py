from pathlib import Path
import hashlib,json,runpy,sys
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/rsegvalidation'
runpy.run_path(str(s/'benchmarks/rsegpagepath/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());mapping=[]
def change(rel,name,fn):
 p=s/rel;inp=Path(m['Replace'].get(str(p),p));before=inp.read_text();after=fn(before);out=o/name;out.write_text(after);m['Replace'][str(p)]=str(out);h.append(dict(path=rel,before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()))
def page(t):
 assert t.count('type RsegPageStats struct {')==1
 t=t.replace('type RsegPageStats struct {','type RsegPageStats struct {\n Validation RsegValidationStats `json:"validation"`')
 assert t.count('type RsegPageCall struct{')==1
 return t.replace('type RsegPageCall struct{','type RsegPageCall struct{\n completion *RsegValidationCall')
change('internal/generatedgo/code/base/rseg_page.go','validation-page.go',page)
def instrument(t,n,expected,patches):
 a=t.index('func '+n+'(');z=t.index('\nfunc ',a+1);f=t[a:z];digest=hashlib.sha256(f.encode()).hexdigest();assert digest==expected,(n,digest)
 anchors=[]
 for old,new,count in patches:
  assert f.count(old)==count,(n,old,f.count(old));f=f.replace(old,new);anchors.append(dict(before=old,after=new,count=count))
 mapping.append(dict(function=n,before_sha256=digest,after_sha256=hashlib.sha256(f.encode()).hexdigest(),anchors=anchors));return t[:a]+f+t[z:]
sig='func Fn18174(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {'
patches=[(sig,sig+'\n vc:=base.RsegValidationBegin(m,l2);defer vc.Finish()',1)]
import re
for call,count in [('Fn18145(m, int32(1), v31, v33)',2),('Fn18145(m, int32(1), v822, v826)',1),('Fn18145(m, int32(1), v1197, v1212)',1)]:
 patches.append((call,'func()int32{defer vc.Phase(0)();return '+call+'}()',count))
call='Fn17470(m, v2800, v2748)';patches.append((call,'func()int32{defer vc.Phase(1)();return '+call+'}()',1))
change('internal/generatedgo/code/p2/p2_pure.go','validation-p2.go',lambda t:instrument(t,'Fn18174','0db2891e971d0433cccd9d0ee91c9ad141a4b08a27b7f5d719a77b5042fb4718',patches))
sig='func Fn18145(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {';digest='e7f55f842faf017b47fa0d01d1bdb23a1fd19967644f617b6e4a6860662ebc09'
# full_crc32 branch, checksum seed ~0 at L23 through final XOR/compare at L36;
# source buf0buf.cc:634-661, all data loads and CRC table lookups remain unchanged.
patches=[(sig,sig+'\n vc:=base.RsegValidationCurrent(m)',1),('\nL23:\n\t;','\nL23:\n\t;\n vc.CRCBegin(v40)',1),('\nL36:\n\t;','\nL36:\n\t;\n vc.CRCEnd()',1)]
change('internal/generatedgo/code/p4/p4_pure.go','validation-p4.go',lambda t:instrument(t,'Fn18145',digest,patches))
for src,dst in [('span.go.txt','rseg_validation.go'),('span-test.go.txt','rseg_validation_test.go')]:
 inp=d/src;target=s/'internal/generatedgo/code/base'/dst;m['Replace'][str(target)]=str(inp);h.append(dict(path=str(target.relative_to(s)),before_sha256=None,after_sha256=hashlib.sha256(inp.read_bytes()).hexdigest()))
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n');(o/'validation-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
