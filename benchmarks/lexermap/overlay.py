from pathlib import Path
import hashlib,json,re,sys
s,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);o.mkdir(parents=True,exist_ok=True)
b=s/'benchmarks/lexermap';proof=json.loads((b/'source-proof.json').read_text())
p=s/'internal/generatedgo/code/p4/p4_pure.go';v=p.read_text()
assert hashlib.sha256(v.encode()).hexdigest()==proof['p4_sha256']
fn=re.search(r'(?ms)^func Fn955\(.*?(?=^func )',v).group()
assert hashlib.sha256(fn.encode()).hexdigest()==proof['function_sha256']
original=fn.replace('func Fn955(', 'func lexerOriginal955(',1)
wrapper='''func Fn955(m *base.Module, l0 int32) int32 {
 if base.LexerMode==0 {return lexerOriginal955(m,l0)}
 if base.LexerMode==2 {
  result:=lexerOriginal955(m,l0)
  base.LexerObserve(m,l0,result,0)
  return result
 }
 start:=base.LexerNow()
 result:=lexerOriginal955(m,l0)
 elapsed:=base.LexerElapsed(start)
 base.LexerObserve(m,l0,result,elapsed)
 return result
}

'''
after=v.replace(fn,wrapper+original,1)
assert original.replace('func lexerOriginal955(','func Fn955(',1)==fn
mapping={};hashes=[]
for relative,data in [('internal/generatedgo/code/p4/p4_pure.go',after),('internal/generatedgo/code/base/lexer_observer.go',(b/'observer.go.txt').read_text()),('internal/generatedgo/code/base/lexer_observer_test.go',(b/'observer_test.go.txt').read_text())]:
 src=s/relative;dest=o/Path(relative).name;dest.write_text(data);mapping[str(src)]=str(dest)
 hashes.append({'path':relative,'before_sha256':hashlib.sha256(src.read_bytes()).hexdigest() if src.exists() else None,'after_sha256':hashlib.sha256(data.encode()).hexdigest()})
(o/'overlay.json').write_text(json.dumps({'Replace':mapping},indent=2)+'\n')
(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
