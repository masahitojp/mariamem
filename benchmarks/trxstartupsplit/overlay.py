from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/trxstartupsplit'
runpy.run_path(str(s/'benchmarks/innodbremainder/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());layout=json.loads((d/'layout.json').read_text());p=s/'internal/generatedgo/code/p2/p2_pure.go'
assert hashlib.sha256(p.read_bytes()).hexdigest()==layout['p2_sha256']
inp=Path(m['Replace'].get(str(p),p));text=inp.read_text();a=text.index('func Fn18291(');z=text.index('\nfunc ',a+1);f=text[a:z]
def patch(before,after):
 global f
 assert f.count(before)==1,before
 f=f.replace(before,after)
q='\nL13:\n\t;';patch(q,q+'\n base.OpenSpanMark(m,"innodb/purge_create_begin")')
q='v481 = Fn17233(m)';patch(q,'base.OpenSpanMark(m,"innodb/purge_create_end")\n v481 = func()int32{defer base.RemainderEnter(m,"rseg_array")();return Fn17233(m)}()')
q='v484 = int32(*(*uint8)(unsafe.Add(mBase, base.MemoryEA(m, 17864585, 0, 1))))';patch(q,q+'\n base.TrxSplitUndoBranch(m,v484)')
new=text[:a]+f+text[z:];out=o/'trxsplit-p2.go';out.write_text(new);m['Replace'][str(p)]=str(out);h.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(text.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
for src,dst in [('span.go.txt','trx_split.go'),('span-test.go.txt','trx_split_test.go')]:
 p=s/'internal/generatedgo/code/base'/dst;inp=d/src;m['Replace'][str(p)]=str(inp);h.append({'path':str(p.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
