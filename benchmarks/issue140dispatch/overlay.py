from pathlib import Path
import sys,json,subprocess,re,hashlib
s,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);subprocess.run(['python3',str(s/'benchmarks/issue140read/overlay.py'),str(s),str(o)],check=True);mapping=json.loads((o/'overlay.json').read_text());records=[]
def body(text,fn):return re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',text,re.M|re.S).group()
def change(name,fn,edit):
 original=(s/name).read_text();oldpath=Path(mapping['Replace'].get(str(s/name),str(s/name)));old=oldpath.read_text();new=edit(old);assert new!=old;out=o/('dispatch-'+str(len(records))+'.go');out.write_text(new);mapping['Replace'][str(s/name)]=str(out);records.append({'path':name,'function':fn,'original_function_sha256':hashlib.sha256(body(original,fn).encode()).hexdigest(),'before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
for fn,info in json.loads((s/'benchmarks/issue140dispatch/source-functions.json').read_text()).items():
 assert hashlib.sha256(body((s/info['path']).read_text(),fn).encode()).hexdigest()==info['sha256']
def submit(text):
 header='func Fn18241(m *base.Module, l0 int32, l1 int32) int32 {';assert text.count(header)==1;return text.replace(header,header+'\nendIO:=base.ObserveIOSubmit(m,l1);defer endIO()',1)
change('internal/generatedgo/code/p8/p8_pure.go','Fn18241',submit)
def worker(text):
 h='func Fn18242(m *base.Module, l0 int32) {';assert text.count(h)==1;text=text.replace(h,h+'\nvar dispatchEnd func()\nbase.ObserveIOWorker(m,l0)',1);a=text.index(h);z=text.index('\nfunc ',a+1);part=text[a:z];assert part.count('L2:\n\t;')==1;part=part.replace('L2:\n\t;','L2:\n\t;\nbase.ObserveIOSyncEnd(m,l0)',1);needle='m.T0[v51].(func(*base.Module, int32, int32))(m, v47, l0+int32(44))';assert part.count(needle)==1;part=part.replace(needle,'dispatchEnd=base.ObserveIOCompletionSubmit(m,l0)\n'+needle+'\ndispatchEnd()',1);return text[:a]+part+text[z:]
change('internal/generatedgo/code/p7/p7_pure.go','Fn18242',worker)
def callback(text):
 h='func Fn18280(m *base.Module, l0 int32) {';assert text.count(h)==1;return text.replace(h,h+'\nendCallback:=base.ObserveIOCallback(m,l0);defer endCallback()',1)
change('internal/generatedgo/code/p6/p6_pure.go','Fn18280',callback)
def host(text):
 text=text.replace('ReadScope *ReadScope','ReadScope *ReadScope\nActiveReadIO *ReadIORequest',1);text=text.replace('child.ReadScope=nil','child.ReadScope=nil\nchild.ActiveReadIO=nil',1);text=text.replace('func (p *ThreadPool) wake(ea uint64, count int32) int32 {','func (p *ThreadPool) wake(ea uint64, count int32, actor ...*Module) int32 {',1);text=text.replace('return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)','return m.Threads.wake(AtomicEA(m, addr, offset, 4), count, m)',1);text=text.replace('ReadObserveSignalBefore(p,ea,ch)','ReadObserveSignalBefore(p,ea,ch,actor...)',1);return text
change('internal/generatedgo/code/base/base.go','AtomicNotify',host)
mapping['Replace'][str(s/'internal/generatedgo/code/base/read_observe.go')]=str(s/'benchmarks/issue140dispatch/read_observe.go.txt')
mapping['Replace'][str(s/'internal/generatedgo/code/base/dispatch_observe_test.go')]=str(s/'benchmarks/issue140dispatch/dispatch_observe_test.go.txt')
(o/'overlay.json').write_text(json.dumps(mapping,indent=2)+'\n');(o/'dispatch-hashes.json').write_text(json.dumps(records,indent=2)+'\n')
