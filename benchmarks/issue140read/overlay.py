from pathlib import Path
import sys,json,hashlib,subprocess
s,o=map(lambda x:Path(x).resolve(),sys.argv[1:]);o.mkdir(exist_ok=True,parents=True);subprocess.run(['python3',str(s/'benchmarks/issue88poolab/overlay.py'),str(s),str(o)],check=True);mapping=json.loads((o/'overlay.json').read_text());records=[]
def save(name,old,new):
 p=s/name;dest=o/('read-'+str(len(records))+'.go');dest.write_text(new);mapping['Replace'][str(p)]=str(dest);records.append({'path':name,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
binding=json.loads((s/'benchmarks/issue140prepare/results/source-binding.json').read_text())
import re
for fn,info in binding['functions'].items():
 text=(s/info['path']).read_text();m=re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',text,re.M|re.S);assert m and hashlib.sha256(m.group().encode()).hexdigest()==info['sha256']
p='internal/generatedgo/code/p8/p8_pure.go';old=(s/p).read_text();new=old.replace('func Fn16787(m *base.Module, l0 int32, l1 int32) {','func Fn16787(m *base.Module,l0,l1 int32){base.ObserveReadWait(m,l0,l1,func(){readOriginal16787(m,l0,l1)})}\nfunc readOriginal16787(m *base.Module, l0 int32, l1 int32) {',1)
a=new.index('func readOriginal16787(');z=new.index('\nfunc ',a+1);part=new[a:z];assert part.count('Fn16583(m)')==1 and part.count('Fn16584(m)')==1;part=part.replace('Fn16583(m)','base.ObserveReadPool(m,true);Fn16583(m)').replace('Fn16584(m)','base.ObserveReadPool(m,false);Fn16584(m)');new=new[:a]+part+new[z:];save(p,old,new)
p='internal/generatedgo/code/p6/p6_pure.go';old=(s/p).read_text();new=old.replace('func Fn16624(m *base.Module, l0 int32) {','func Fn16624(m *base.Module,l0 int32){end:=base.ObserveReadLatch(m,l0);defer end();readOriginal16624(m,l0)}\nfunc readOriginal16624(m *base.Module, l0 int32) {',1);assert new!=old;save(p,old,new)
p='internal/generatedgo/code/base/base.go';old=(s/p).read_text();new=old.replace('ThreadLifetime         *ThreadLifetime\n','ThreadLifetime         *ThreadLifetime\nReadScope *ReadScope\n',1);assert new!=old
new=new.replace('m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\n','m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\nreadWait:=ReadObserveRegister(m,ea,ch)\ndefer ReadObserveReturn(readWait)\n',1)
# Both untimed and timed successful wake branches, within AtomicWait only.
a=new.index('func AtomicWait(m ');z=new.index('\n// threadLaunch',a);part=new[a:z];assert part.count('case <-ch:')==2;part=part.replace('case <-ch:','case <-ch:\nReadObserveResume(readWait)');new=new[:a]+part+new[z:]
new=new.replace('*child = *m\n','*child = *m\nchild.ReadScope=nil\n',1).replace('body(child, tid)','ClearReadThreadLabel(child)\nbody(child, tid)',1)
a=new.index('func (p *ThreadPool) wake(');z=new.index('\n}',a)+2;part=new[a:z];assert part.count('close(ch)')==1;part=part.replace('close(ch)','readSignal:=ReadObserveSignalBefore(p,ea,ch)\nclose(ch)\nReadObserveSignalAfter(readSignal)');new=new[:a]+part+new[z:];save(p,old,new)
p='internal/generatedgo/runtime_instance.go';old=(s/p).read_text();new=old.replace('newMemoryModule, captures...)','func(h *host)(*base.Module,func()error,error){m,release,err:=newMemoryModule(h);if err!=nil{return m,release,err};off:=base.RegisterReadObservation(m,readDB);return m,func()error{off();return release()},nil}, captures...)',1)
# Add an internal observed entry while preserving the original entry signature.
a=new.index('func StartInstance(');z=new.index('\nfunc startInstance',a);original=old[old.index('func StartInstance('):old.index('\nfunc startInstance')];observed=new[a:z].replace('func StartInstance(', 'func StartObservedInstance(readDB string, ');new=new[:a]+original+'\n'+observed+new[z:];save(p,old,new)
p='internal/guest/linked.go';old=(s/p).read_text();new=old.replace('"os"','"os"\n"runtime/pprof"',1).replace('execution := generatedgo.StartInstance(', 'readDB,_:=pprof.Label(ctx,"db_id")\nexecution := generatedgo.StartObservedInstance(readDB,',1);assert new!=old;save(p,old,new)
for name in ('read_observe.go','read_observe_test.go'):
 mapping['Replace'][str(s/'internal/generatedgo/code/base'/name)]=str(s/'benchmarks/issue140read'/(name+'.txt'))
(o/'overlay.json').write_text(json.dumps(mapping,indent=2)+'\n');(o/'read-hashes.json').write_text(json.dumps(records,indent=2)+'\n')
