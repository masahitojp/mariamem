from pathlib import Path
import sys,subprocess,re,json,hashlib
S,P,T=map(lambda x:Path(x).resolve(),sys.argv[1:]);O=T/'overlay';O.mkdir(exist_ok=True)
OLD='bcab9e6e07f9bf237c98a39eeba62cbcfd1e3997'
def get(path):return subprocess.check_output(['git','show',OLD+':'+path],cwd=S,text=True)
def body(s,n):return re.search(r'^func '+n+r'\(.*?(?=\nfunc |\Z)',s,re.M|re.S)[0]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
rebound={}
def bind(n,path):
 a=body(get(path),n);b=body((P/path).read_text(),n)
 nums=lambda s:re.split(r'(?<![A-Za-z_])\b(\d+)\b',s)
 aa,bb=nums(a),nums(b);assert len(aa)==len(bb),(n,'structure changed')
 changes=[]
 for x,y in zip(aa,bb):
  if x==y:continue
  assert x.isdigit() and y.isdigit() and (((int(x)>=17800000 or int(x)==16106532) and int(y)-int(x)==749632) or (int(x),int(y)) in [(8953328,8953392),(8930318,8930352)]),(n,x,y)
  changes.append([int(x),int(y)])
 rebound[n]={'path':path,'old_sha256':sha(a),'current_sha256':sha(b),'relocations':sorted(set(map(tuple,changes)))}
 return b
for manifest in ['benchmarks/issue140prepare/results/source-binding.json','benchmarks/issue140dispatch/source-functions.json','benchmarks/issue140admission/source-functions.json']:
 j=json.loads(get(manifest));f=j.get('functions',j)
 for n,r in f.items():
  assert sha(body(get(r['path']),n))==r['sha256'];b=bind(n,r['path']);r['sha256']=sha(b)
 out=P/manifest;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(j,indent=2)+'\n')
paths=['benchmarks/issue140read/overlay.py','benchmarks/issue140dispatch/overlay.py','benchmarks/issue140admission/overlay.py','benchmarks/issue140admission/read_observe.go.txt','benchmarks/issue140read/read_observe_test.go.txt','benchmarks/issue140dispatch/dispatch_observe_test.go.txt','benchmarks/issue140admission/admission_observe_test.go.txt']
for name in paths:
 v=get(name)
 if name=='benchmarks/issue140read/overlay.py':
  a="subprocess.run(['python3',str(s/'benchmarks/issue88poolab/overlay.py'),str(s),str(o)],check=True);mapping=json.loads((o/'overlay.json').read_text());records=[]"
  assert a in v;v=v.replace(a,"mapping={'Replace':{}};records=[]")
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v)
subprocess.run([sys.executable,P/'benchmarks/issue140admission/overlay.py',P,O],check=True)
mapping=json.loads((O/'overlay.json').read_text());changes=[]
def change(path,n,edit):
 original=(P/path).read_text();old=Path(mapping['Replace'].get(str(P/path),str(P/path))).read_text()
 b=body(old,n);newbody=edit(b);assert b!=newbody,n
 new=old.replace(b,newbody,1);out=O/('progress-'+str(len(changes))+'.go');out.write_text(new);mapping['Replace'][str(P/path)]=str(out)
 changes.append({'path':path,'function':n,'before_sha256':sha(old),'after_sha256':sha(new)})
def replace(b,a,c,count=1):
 assert b.count(a)==count,(a,b.count(a));return b.replace(a,c)
# The old outer-gate collector scans the complete queue under the guest lock.
# Replace it with one bounded state event, correlated offline with exact
# enqueue/dequeue events; no claims of queue membership from unfinished I/O.
p=P/'benchmarks/issue140admission/read_observe.go.txt';r=p.read_text();i=r.index('func ObserveGlobalGate(');r=r[:i]+'''func ObserveGlobalGate(m *Module,pool int32){ProgressLocked(m,pool,0,"gate",0)}\n''';r=r.replace('type ReadObserver struct {','type ReadObserver struct {\n Progress []ProgressEvent `json:"progress"`',1)
p.write_text(r)
# Runtime collector structure and inherited worker identity reset.
basepath='internal/generatedgo/code/base/base.go';original=Path(mapping['Replace'][str(P/basepath)]).read_text()
b=replace(original,'ReadScope *ReadScope','ReadScope *ReadScope\nProgressWorker int32\nProgressPool int32\nProgressActor string')
b=replace(b,'child.ReadScope=nil','child.ReadScope=nil\nchild.ProgressWorker=0\nchild.ProgressPool=0\nchild.ProgressActor=""')
p=O/'progress-base.go';p.write_text(b);mapping['Replace'][str(P/basepath)]=str(p)
for n,part in [('Fn16595','p6'),('Fn16597','p4'),('Fn16603','p5'),('Fn16605','p7'),('Fn16606','p7'),('Fn16607','p8')]:bind(n,f'internal/generatedgo/code/{part}/{part}_pure.go')
def worker(b):
 h='func Fn16595(m *base.Module, l0 int32, l1 int32) {'
 b=replace(b,h,h+'\nm.ProgressWorker=l1;m.ProgressPool=l0\nbase.Progress(m,l0,l1,0,"worker_enter",0)\ndefer base.Progress(m,l0,l1,0,"worker_exit",0)')
 needle='base.AtomicStore32_8(m, l0, int32(408), v25)'
 b=replace(b,needle,needle+'\nbase.Progress(m,l0,l1,0,"pending_clear",0)')
 needle='m.T0[v18].(func(*base.Module))(m)'
 b=replace(b,needle,'base.Progress(m,l0,l1,0,"init_begin",0)\n'+needle+'\nbase.Progress(m,l0,l1,0,"init_return",int64(m.ExcPending))')
 needle='m.T0[v47].(func(*base.Module, int32))(m, v43)'
 return replace(b,needle,'base.Progress(m,l0,l1,v43,"task_begin",0)\n'+needle+'\nbase.Progress(m,l0,l1,v43,"task_end",int64(m.ExcPending))')
change('internal/generatedgo/code/p6/p6_pure.go','Fn16595',worker)
def add(b):
 h='func Fn16597(m *base.Module, l0 int32) {'
 b=replace(b,h,h+'\nbase.ProgressLocked(m,l0,0,"add_enter",0)')
 for needle,kind,aux in [('if base.Ui32(v18) <= base.Ui32(v17) {','add_max','int64(v18)'),('if v55-v57 < v74 {','add_throttle','v74'),('if v83&v81 != 0 {','add_pending','int64(v83)')]:
  b=replace(b,needle,needle+'\nbase.ProgressLocked(m,l0,0,"'+kind+'",'+aux+')')
 needle='v83 = base.AtomicRmwXchg32_8u(m, l0, int32(408), v81)'
 b=replace(b,needle,needle+'\nbase.ProgressLocked(m,l0,0,"pending_exchange",int64(v83))')
 needle='v196 = Fn16598(m, v13+int32(16), v13+int32(24), v13+int32(12), v13+int32(20))'
 b=replace(b,needle,'base.ProgressLocked(m,l0,0,"spawn_call",0)\n'+needle+'\nbase.ProgressLocked(m,l0,0,"spawn_return",int64(v196))')
 needle='base.AtomicStore32_8(m, l0, int32(408), v327)'
 return replace(b,needle,needle+'\nbase.ProgressLocked(m,l0,0,"spawn_failure_clear",0)')
change('internal/generatedgo/code/p4/p4_pure.go','Fn16597',add)
def wake(b):
 needle='Fn16554(m, v16)';return replace(b,needle,'base.ProgressLocked(m,l0,v16,"wake_call",0)\n'+needle)
change('internal/generatedgo/code/p7/p7_pure.go','Fn16596',wake)
def dequeue(b):
 needle='base.ObserveGlobalDequeue(m,l0,v268)';return replace(b,needle,needle+'\nbase.ProgressLocked(m,l0,v268,"dequeue",0)')
change('internal/generatedgo/code/p4/p4_pure.go','Fn16594',dequeue)
def submit(b):
 h='func Fn16605(m *base.Module, l0 int32, l1 int32) {'
 b=replace(b,h,h+'\npreviousActor:=m.ProgressActor;m.ProgressActor="submit";defer func(){m.ProgressActor=previousActor}()')
 needle='Fn16596(m, l0)';return replace(b,needle,'base.ProgressLocked(m,l0,l1,"enqueue",0)\n'+needle,2)
change('internal/generatedgo/code/p7/p7_pure.go','Fn16605',submit)
def waitbegin(b):
 h='func Fn16606(m *base.Module, l0 int32) {'
 b=replace(b,h,h+'\npreviousActor:=m.ProgressActor;m.ProgressActor="wait_begin";defer func(){m.ProgressActor=previousActor}()')
 needle='Fn16596(m, l0)';return replace(b,needle,'base.ProgressLocked(m,l0,0,"wait_begin_applied",0)\n'+needle)
change('internal/generatedgo/code/p7/p7_pure.go','Fn16606',waitbegin)
def waitend(b):
 needle='= v21 - int32(1)';
 if needle not in b:raise ValueError('inspect wait_end decrement first')
 return replace(b,needle,needle+'\nbase.ProgressLocked(m,l0,0,"wait_end_applied",0)')
# Find the existing locked waiting-count decrement without reading it externally.
b=body((P/'internal/generatedgo/code/p8/p8_pure.go').read_text(),'Fn16607')
(T/'waitend-body.txt').write_text(b)
def waitend(b):
 pattern=r'(\*\(\*int32\)\(unsafe.Add\(mBase, base.MemoryEA\(m, uint64\(uint32\(l0\)\), 372, 4\)\)\) = v\d+ - int32\(1\))'
 matches=re.findall(pattern,b);assert len(matches)==1
 return replace(b,matches[0],matches[0]+'\nbase.ProgressLocked(m,l0,0,"wait_end_applied",0)')
change('internal/generatedgo/code/p8/p8_pure.go','Fn16607',waitend)
def maintenance(b):
 h='func Fn16603(m *base.Module, l0 int32) {'
 b=replace(b,h,h+'\npreviousActor:=m.ProgressActor;m.ProgressActor="maintenance";defer func(){m.ProgressActor=previousActor}()\nbase.Progress(m,l0,0,0,"maintenance_enter",0)\ndefer base.Progress(m,l0,0,0,"maintenance_return",0)')
 # The outer gate hook has the locked state, and this wrapper's scope is
 # sufficient to distinguish calls from maintenance versus submission.
 return b
change('internal/generatedgo/code/p5/p5_pure.go','Fn16603',maintenance)
# Include the event helper. Compilation uses overlays only.
mapping['Replace'][str(P/'internal/generatedgo/code/base/progress_observe.go')]=str(T/'progress.go.txt')
(O/'overlay.json').write_text(json.dumps(mapping,indent=2)+'\n')
(T/'rebound.json').write_text(json.dumps(rebound,indent=2)+'\n');(T/'progress-overlay.json').write_text(json.dumps(changes,indent=2)+'\n')
print('OVERLAY READY: full preimages, only reviewed +749632 static-address relocations; locked event hooks')
