from pathlib import Path
import sys,json,subprocess,re,hashlib
s,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);subprocess.run(['python3',str(s/'benchmarks/issue140dispatch/overlay.py'),str(s),str(o)],check=True);mapping=json.loads((o/'overlay.json').read_text());records=[]
def body(text,fn):return re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',text,re.M|re.S).group()
for fn,info in json.loads((s/'benchmarks/issue140admission/source-functions.json').read_text()).items():assert hashlib.sha256(body((s/info['path']).read_text(),fn).encode()).hexdigest()==info['sha256']
def change(name,fn,edit):
 original=(s/name).read_text();old=Path(mapping['Replace'].get(str(s/name),str(s/name))).read_text();new=edit(old);assert old!=new;out=o/('admission-'+str(len(records))+'.go');out.write_text(new);mapping['Replace'][str(s/name)]=str(out);records.append({'path':name,'function':fn,'original_function_sha256':hashlib.sha256(body(original,fn).encode()).hexdigest(),'before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
def group(text):
 h='func Fn16586(m *base.Module, l0 int32) {';a=text.index(h);z=text.index('\nfunc ',a+1);b=text[a:z];b=b.replace(h,h+'\nbase.ObserveGroupEnter(m,l0)',1);needle='v17 = base.B2i32(v15 != v16)';assert b.count(needle)==1;b=b.replace(needle,'base.ObserveGroupGate(m,l0,v9,uint32(v15),uint32(v16))\n'+needle,1);needle='m.T0[v71].(func(*base.Module, int32))(m, v70)';assert b.count(needle)==1;b=b.replace(needle,'base.ObserveGroupRun(m,v58)\n'+needle,1);return text[:a]+b+text[z:]
change('internal/generatedgo/code/p6/p6_pure.go','Fn16586',group)
def dequeue(text):
 h='func Fn16594(';a=text.index(h);z=text.index('\nfunc ',a+1);b=text[a:z];needle='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l2)), 0, 4))) = v268';assert b.count(needle)==1;b=b.replace(needle,needle+'\nbase.ObserveGlobalDequeue(m,l0,v268)',1);return text[:a]+b+text[z:]
change('internal/generatedgo/code/p4/p4_pure.go','Fn16594',dequeue)
def gate(text):
 h='func Fn16596(m *base.Module, l0 int32) {';assert text.count(h)==1;return text.replace(h,h+'\nbase.ObserveGlobalGate(m,l0)',1)
change('internal/generatedgo/code/p7/p7_pure.go','Fn16596',gate)
mapping['Replace'][str(s/'internal/generatedgo/code/base/read_observe.go')]=str(s/'benchmarks/issue140admission/read_observe.go.txt')
mapping['Replace'][str(s/'internal/generatedgo/code/base/admission_observe_test.go')]=str(s/'benchmarks/issue140admission/admission_observe_test.go.txt')
(o/'overlay.json').write_text(json.dumps(mapping,indent=2)+'\n');(o/'admission-hashes.json').write_text(json.dumps(records,indent=2)+'\n')
