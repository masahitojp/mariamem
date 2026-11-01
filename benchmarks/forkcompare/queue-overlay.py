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

def concurrency(f):
 old='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 344, 4))) = v25'
 assert f.count(old)==2
 return f.replace(old,old+'\n base.DiagEvent(m,"concurrency_store",0,int64(l1),int64(v25),int64(l0),true)\n base.DiagEvent(m,"concurrency_inputs",0,int64(v15),int64(v20),int64(v17),false)')
func_edit(16603,concurrency)
def return_observe(n,kind,a):
 def change(f):
  assert f.count(') int32 {')==1
  return f.replace(') int32 {',') (diagResult int32) {\n defer func(){base.DiagEvent(m,"'+kind+'",0,'+a+',int64(diagResult),0,true)}()',1)
 func_edit(n,change)
return_observe(16544,'hardware_concurrency','0')
return_observe(279,'sysconf','int64(l0)')
edit('internal/generatedgo/main.go','binary.LittleEndian.PutUint32(m.Memory[out:], uint32(runtime.NumCPU()))','base.DiagEvent(m,"host_cpu_count",0,int64(runtime.NumCPU()),0,0,true)\n binary.LittleEndian.PutUint32(m.Memory[out:], uint32(runtime.NumCPU()))')

rel='internal/generatedgo/code/base/diag_sql_wake.go';files[rel]=(B/'trace-queue.go.txt').read_text()
# Same runtime argv selector and existing phase-file bridge as the prior trial.
files['internal/generatedgo/code/experiment_read_io.go']=(B/'candidate-data.go.txt').read_text()
files['internal/timing/experiment_guest_source.go']=(B/'guest-filebridge.go.txt').read_text()
rel='internal/timing/timing.go';old='data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))'
edit(rel,old,old+'\n if err!=nil{data,err=experimentReadGuest(transfer)}')
rel='internal/generatedgo/runtime_instance.go'
edit(rel,'"sync"','"sync"\n "os"\n "github.com/masahitojp/mariamem/internal/timing"')
edit(rel,'w.SetFS(entropyFS{fs})','''w.SetFS(entropyFS{fs})
 if guestTiming {
 unregister:=timing.ExperimentGuestSource(transfer,func()([]byte,error){
 f,e:=fs.OpenFile("snapshot-out/startup-timing.json",os.O_RDONLY,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(f)
 });defer unregister()
 }''')
edit(rel,'m.Threads.NotifyWorkerFailure(', 'base.DiagBindChild(m,transfer)\n m.Threads.NotifyWorkerFailure(')
# The public caller's pprof child label is available here; transfer is per-instance.
rel='internal/guest/linked.go'
edit(rel,'"os"','"os"\n "runtime/pprof"\n "github.com/masahitojp/mariamem/internal/generatedgo/code/base"')
edit(rel,'execution := generatedgo.StartInstance(', 'childLabel,_:=pprof.Label(ctx,"child")\n unlabel:=base.DiagAssociateTransfer(transfer,childLabel);defer unlabel()\n execution := generatedgo.StartInstance(')
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
