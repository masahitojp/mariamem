"""Diagnostic only; reconstruct from clean pinned product, assert exact edit anchors."""
import hashlib,json,re,sys
from pathlib import Path
B=Path(__file__).resolve().parent
W=B.parents[2];P=W/'temp/product';O=W/'temp/overlay';O.mkdir(parents=True,exist_ok=True)
files={};checks={}
def get(rel):
 if rel not in files:files[rel]=(P/rel).read_text()
 return files[rel]
def edit(rel,old,new,count=1):
 s=get(rel);assert s.count(old)==count,(rel,old,s.count(old),count)
 files[rel]=s.replace(old,new)
def func_edit(num,transform):
 hits=[]
 for p in (P/'internal/generatedgo/code').glob('p*/p*_pure.go'):
  rel=str(p.relative_to(P));s=get(rel)
  m=re.search(r'^func Fn'+str(num)+r'\(.*?\{\n',s,re.M)
  if m:
   end=s.find('\nfunc ',m.end());end=end if end!=-1 else len(s)
   frag=s[m.start():end];files[rel]=s[:m.start()]+transform(frag)+s[end:];hits.append(rel)
 assert len(hits)==1,(num,hits)
def begin(num,name,args='int64(l0),0,0'):
 func_edit(num,lambda f:f.replace('{\n','{\n\tdefer base.DiagBegin(m,"'+name+'",'+args+')()\n',1))
for n,name,args in [(16604,'submit','int64(l0),int64(l1),0'),(16602,'maintenance','int64(l0),0,0'),(16605,'wait_begin','int64(l0),0,0'),(16606,'wait_end','int64(l0),0,0'),(16596,'add_thread','int64(l0),0,0'),(16594,'worker_main','int64(l0),int64(l1),0'),(16786,'read_wait','int64(l0),int64(l1),0')]:begin(n,name,args)
func_edit(16595,lambda f:f.replace('{\n','{\n\tbase.DiagPool(m,l0)\n',1))
def task(f):
 old='\tm.T0[v47].(func(*base.Module, int32))(m, v43)';assert f.count(old)==1
 return f.replace(old,'\tbase.DiagEvent(m,"task_start",0,int64(l0),int64(v43),int64(v47),false)\n'+old+'\n\tbase.DiagEvent(m,"task_end",0,int64(l0),int64(v43),int64(v47),false)')
func_edit(16594,task)
base='internal/generatedgo/code/base/base.go'
edit(base,'func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {','func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) (diagRC int32) {\n diagID:=DiagEvent(m,"wait_enter",0,int64(ea),timeout,0,true)\n defer func(){DiagEvent(m,"wait_return",diagID,int64(ea),timeout,int64(diagRC),false)}()')
edit(base,'m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)','m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\n DiagEvent(m,"park_registered",diagID,int64(ea),timeout,0,false)')
edit(base,'return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)','ea:=AtomicEA(m, addr, offset, 4)\n id:=DiagEvent(m,"notify_enter",0,int64(ea),int64(count),0,true)\n n:=m.Threads.wake(ea,count)\n DiagEvent(m,"notify_return",id,int64(ea),int64(count),int64(n),false)\n return n')
edit(base,'func (w *WasiStubs) Fd_pread(m *Module, fd, iovs, iovsLen int32, offset int64, nreadPtr int32) int32 {','func (w *WasiStubs) Fd_pread(m *Module, fd, iovs, iovsLen int32, offset int64, nreadPtr int32) int32 {\n defer DiagBegin(m,"pread",int64(fd),offset,int64(iovsLen))()')
edit(base,'body(child, tid)','DiagEvent(child,"thread_start",0,int64(tid),0,0,true)\n\t\tbody(child, tid)')
rel='internal/generatedgo/code/base/diag_sql_wake.go';files[rel]=(B/'trace.go.txt').read_text()
overlay={}
for rel,content in files.items():
 original=(P/rel).read_text() if (P/rel).exists() else ''
 if content==original:continue
 out=O/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(content)
 overlay[str(P/rel)]=str(out)
 checks[rel]={'before_sha256':hashlib.sha256(original.encode()).hexdigest() if original else None,'after_sha256':hashlib.sha256(content.encode()).hexdigest()}
(W/'temp/overlay.json').write_text(json.dumps({'Replace':overlay},indent=2)+'\n')
(W/'evidence/overlay-hashes.json').write_text(json.dumps(checks,indent=2)+'\n')
print('overlay',len(overlay),'files')
