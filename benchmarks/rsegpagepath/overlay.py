from pathlib import Path
import hashlib,json,runpy,sys
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/rsegpagepath'
runpy.run_path(str(s/'benchmarks/rsegcostsplit/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text())
def replace(rel,old,new,outname):
 p=s/rel;inp=Path(m['Replace'].get(str(p),p));before=inp.read_text();assert before.count(old)==1,(rel,old)
 after=before.replace(old,new);out=o/outname;out.write_text(after);m['Replace'][str(p)]=str(out);h.append(dict(path=rel,before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()))
replace('internal/generatedgo/code/base/rseg_cost.go','type RsegCost struct {','type RsegCost struct {\n HeaderPath RsegPageStats `json:"header_path"`','rseg-cost-with-path.go')
replace('internal/generatedgo/code/p2/p2_pure.go','func()int32{defer rc.Page(2)(); return Fn18164','func()int32{release:=base.RsegPageBind(m,rc);defer release();defer rc.Page(2)(); return Fn18164','header-p2.go')
p=s/'internal/generatedgo/code/p3/p3_pure.go';assert hashlib.sha256(p.read_bytes()).hexdigest()=='df1076eca2e4cb5fa8cce55ebc85fb672ed448a718780378c66cd6cb7dbe482c'
inp=Path(m['Replace'].get(str(p),p));before=inp.read_text();a=before.index('func Fn18164(');z=before.index('\nfunc ',a+1);f=before[a:z]
assert hashlib.sha256(f.encode()).hexdigest()=='009f526a743832d642383d086edababe28198848855d6fff8bf615fc325e34ea'
anchors=[]
def patch(old,new):
 global f
 assert f.count(old)==1,old;f=f.replace(old,new);anchors.append(old)
q=f.splitlines()[0];patch(q,q+'\n pp:=base.RsegPageBegin(m,l1,l2,l3)\n defer pp.Finish()')
patch('\nL18:\n\t;','\nL18:\n\t;\n pp.Begin(0)')
patch('\nL111:\n\t;','\nL111:\n\t;\n pp.Lookup(true)')
patch('\nL114:\n\t;','\nL114:\n\t;\n pp.Lookup(false)')
q='Fn16792(m, v99, v104, v110, int32(1))';patch(q,'func()int32{defer pp.Phase(1)();return '+q+'}()')
for kind,q in [(2,'Fn16788(m, v99)'),(3,'Fn16787(m, v580, v108)')]:patch(q,'func(){defer pp.Phase('+str(kind)+')();'+q+'}()')
after=before[:a]+f+before[z:];out=o/'header-p3.go';out.write_text(after);m['Replace'][str(p)]=str(out);h.append(dict(path=str(p.relative_to(s)),before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()))
p5=s/'internal/generatedgo/code/p5/p5_pure.go'
assert hashlib.sha256(p5.read_bytes()).hexdigest()=='8ddc2f0ab2f67d840a9a545a32410efe3a39cd5fb4d230f3cd0ca6c40ec1fa6e'
before5=Path(m['Replace'].get(str(p5),p5)).read_text();a5=before5.index('func Fn16789(');z5=before5.index('\nfunc ',a5+1);f5=before5[a5:z5]
assert hashlib.sha256(f5.encode()).hexdigest()=='1681f0b19d7c6d8db407d375c26a53029fea6e01be994d09b97ad691b77c4138'
nested=[
 (0,'Fn16791(m, l0, l1, l3, l5)',3,True),
 (1,'Fn17564(m, v16+int32(24), l4, v16+int32(8), base.I64_extend_i32_u(v81)*(l0&int64(4294967295)), v81, v88, v47)',12,False),
 (2,'Fn18174(m, v47, v154, v157)',6,True),
 (3,'Fn16787(m, v47, v45)',6,False),
]
for kind,call,count,returns in nested:
 assert f5.count(call)==count,(call,f5.count(call))
 replacement='func()'+('int32' if returns else '')+'{defer base.RsegPageNested(m,'+str(kind)+')();'+('return ' if returns else '')+call+'}()'
 f5=f5.replace(call,replacement)
after5=before5[:a5]+f5+before5[z5:];out5=o/'header-p5.go';out5.write_text(after5);m['Replace'][str(p5)]=str(out5);h.append(dict(path=str(p5.relative_to(s)),before_sha256=hashlib.sha256(before5.encode()).hexdigest(),after_sha256=hashlib.sha256(after5.encode()).hexdigest()))
for src,dst in [('span.go.txt','rseg_page.go'),('span-test.go.txt','rseg_page_test.go')]:
 inp=d/src;target=s/'internal/generatedgo/code/base'/dst;m['Replace'][str(target)]=str(inp);h.append(dict(path=str(target.relative_to(s)),before_sha256=None,after_sha256=hashlib.sha256(inp.read_bytes()).hexdigest()))
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
(o/'page-mapping.json').write_text(json.dumps(dict(function='Fn18164',native='buf_page_get_gen',p3_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),raw_body_sha256='12968dba4a55a206bfba1edcabe889d039e2887fdc23c03f26c071349a0828ce',inherited_owner_body_sha256='009f526a743832d642383d086edababe28198848855d6fff8bf615fc325e34ea',anchors=anchors,phases=['lookup','sync_read_miss','random_read_ahead','read_wait'],nested_read=dict(function='Fn16789',body_sha256='1681f0b19d7c6d8db407d375c26a53029fea6e01be994d09b97ad691b77c4138',anchors=nested,phases=['frame_init','sync_io_request','read_complete','race_read_wait']),scope='exact rseg header caller Module only; nonreentrant top call; other/latch residual explicit; nested phases counted within read miss'),indent=2)+'\n')
