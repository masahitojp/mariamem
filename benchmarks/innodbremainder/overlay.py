from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/innodbremainder'
runpy.run_path(str(s/'benchmarks/innodbopenspan/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());layout=json.loads((d/'layout.json').read_text())
p=s/'internal/generatedgo/code/p0/p0_pure.go';assert hashlib.sha256(p.read_bytes()).hexdigest()==layout['p0_sha256']
inp=Path(m['Replace'].get(str(p),p));text=inp.read_text();a=text.index('func Fn18569(');z=text.index('\nfunc ',a+1);f=text[a:z]
def patch(before,after):
 global f
 assert f.count(before)==1,before
 f=f.replace(before,after)
for label,name in layout['marks']:
 q='\n'+label+':\n\t;';patch(q,q+'\n base.OpenSpanMark(m,"innodb/'+name+'")')
for line,name in layout['calls']:
 lhs,rhs=line.split(' = ');patch(line,lhs+' = func()int32{defer base.RemainderEnter(m,"'+name+'")();return '+rhs+'}()')
q=layout['apply_needle'];patch(q,q.replace('Fn17465(m, int32(1))','func(){defer base.RemainderEnter(m,"redo_apply")();Fn17465(m,int32(1))}()'))
patch('Fn227(m, int32(8620240))','Fn227(m, int32(8620240))\n base.OpenSpanMark(m,"innodb/outer_begin")')
patch('Fn227(m, int32(8619848))','base.OpenSpanMark(m,"innodb/outer_end")\n Fn227(m, int32(8619848))')
new=text[:a]+f+text[z:];out=o/'remainder-p0.go';out.write_text(new);m['Replace'][str(p)]=str(out);h.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(text.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
for src,dst in [('span.go.txt','remainder_span.go'),('span-test.go.txt','remainder_span_test.go')]:
 p=s/'internal/generatedgo/code/base'/dst;inp=d/src;m['Replace'][str(p)]=str(inp);h.append({'path':str(p.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
