from pathlib import Path
import sys,runpy,json,hashlib,re
S,O=map(lambda p:Path(p).resolve(),sys.argv[1:]);runpy.run_path(str(S/'benchmarks/bufferflush/overlay.py'),run_name='__main__');maps=json.loads((O/'overlay.json').read_text());hashes=json.loads((O/'hashes.json').read_text())
def patch(rel,fn):
 p=S/rel;orig=p.read_text();old=Path(maps['Replace'][str(p)]).read_text() if str(p) in maps['Replace'] else orig;new=fn(old);out=O/('uw-'+p.name);out.write_text(new);maps['Replace'][str(p)]=str(out);hashes[:]=[h for h in hashes if h['path']!=rel];hashes.append({'path':rel,'before_sha256':hashlib.sha256(orig.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})
def replace(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def entry(s,n,code):
 m=re.search(r'^func Fn'+str(n)+r'\([^\n]*\{\n',s,re.M);assert m,n;return s[:m.end()]+code+s[m.end():]
patch('internal/generatedgo/runtime_instance.go',lambda s:replace(s,'\t\tm.Threads.NotifyWorkerFailure','\t\tdiagChild,diagOK:=ctx.Value("forkstages_child").(int)\n base.UWBind(m,diagChild,diagOK)\n defer base.UWFlush(m)\n\t\tm.Threads.NotifyWorkerFailure'))
patch('internal/generatedgo/code/p7/p7_pure.go',lambda s:entry(s,5853,' defer base.UWSqlBegin(m,l1,l2)()\n'))
patch('internal/generatedgo/code/p8/p8_pure.go',lambda s:entry(s,17227,' defer base.UWRsegBegin(m,l0)()\n'))
patch('internal/generatedgo/code/p6/p6_pure.go',lambda s:entry(s,16621,' defer base.UWMutexBegin(m,l0)()\n'))
def core(s):
 s=replace(s,'return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)','return m.Threads.wake(AtomicEA(m, addr, offset, 4), count, m)')
 s=replace(s,'func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {','func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) (uwRC int32) {')
 s=replace(s,'m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)','m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\n uwID:=UWRegister(m,ea,timeout,ch)\n defer func(){UWWaitEvent(m,uwID,"wait_return",uwRC)}()')
 a=s.index('func AtomicWait(');b=s.index('\n// threadLaunch',a);frag=s[a:b];assert frag.count('case <-ch:')==2;frag=frag.replace('case <-ch:','case <-ch:\n UWWaitEvent(m,uwID,"wait_resume",0)');s=s[:a]+frag+s[b:]
 s=replace(s,'func (p *ThreadPool) wake(ea uint64, count int32) int32 {','func (p *ThreadPool) wake(ea uint64, count int32, uwModules ...*Module) int32 {\n uwToken:=UWNotifyBegin(p,ea,uwModules);var uwWoke int32\n defer func(){UWNotifyEnd(uwToken,ea,uwWoke)}()')
 s=replace(s,'for _, ch := range waiters[:n] {\n\t\tclose(ch)','for _, ch := range waiters[:n] {\n UWSignal(p,ea,ch,uwToken,false)\n\t\tclose(ch)\n UWSignal(p,ea,ch,uwToken,true)')
 a=s.index('func (p *ThreadPool) wake(');b=s.index('\n// SaveGlobals',a);frag=s[a:b];assert frag.count('\treturn n')==1;frag=frag.replace('\treturn n',' uwWoke=n\n\treturn n');return s[:a]+frag+s[b:]
patch('internal/generatedgo/code/base/base.go',core)
for src,dst in [('trace.go.txt','update_notify.go'),('trace-test.go.txt','update_notify_test.go')]:
 p=S/'benchmarks/updatenotify'/src;target=S/'internal/generatedgo/code/base'/dst;maps['Replace'][str(target)]=str(p);hashes.append({'path':str(target.relative_to(S)),'before_sha256':None,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(O/'overlay.json').write_text(json.dumps(maps,indent=2)+'\n');(O/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
