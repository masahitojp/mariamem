"""Exact-preimage overlay for an isolated, same-process heap Snapshot spike."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BASE='a8137b8b444f86068d3128a291e3a848adfdfd56';changes={}
def read(n):
 p=ROOT/n;old=subprocess.check_output(['git','show',BASE+':'+n],cwd=ROOT);assert p.read_bytes()==old,n
 changes[n]={'before':hashlib.sha256(old).hexdigest()};return old.decode()
def save(n,s):(ROOT/n).write_text(s)
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
n='internal/generatedgo/code/base/base.go';s=read(n)
s=replace(s,'type MemFS struct {','type MemFS struct {\n dEnabled bool')
s=replace(s,'type memNode struct {','type memNode struct {\n d *dStorage')
s=replace(s,'\t\tparent.children[base] = node\n','\t\tparent.children[base] = node\n fsys.dEnroll(node)\n')
a='\tcp := make([]byte, len(data))\n\tcopy(cp, data)\n\tparent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}'
b='\tnode:= &memNode{parent:parent,name:base,mode:perm & 0o777,modTime:time.Now()}\n fsys.dEnroll(node)\n if node.d!=nil {if _,err:=node.d.writeAt(data,0);err!=nil{return err}}else{cp:=make([]byte,len(data));copy(cp,data);node.data=cp}\n parent.children[base]=node'
s=replace(s,a,b)
s=s.replace('node.data = node.data[:0]','if node.d!=nil {if err:=node.d.resize(0);err!=nil{return nil,err}}else{node.data=node.data[:0]}')
s=s.replace('int64(len(node.data))','node.dSize()').replace('int64(len(n.data))','n.dSize()').replace('int64(len(f.node.data))','f.node.dSize()')
s=s.replace('f.node.data = resizeMemData(f.node.data, end)','if f.node.d!=nil {if err:=f.node.d.resize(end);err!=nil{panic(err)}}else{f.node.data=resizeMemData(f.node.data,end)}')
s=s.replace('f.node.data = resizeMemData(f.node.data, size)','if f.node.d!=nil {if err:=f.node.d.resize(size);err!=nil{return err}}else{f.node.data=resizeMemData(f.node.data,size)}')
s=s.replace('if f.off >= f.node.dSize() {','if f.node.d!=nil {n,e:=f.node.d.readAt(p,f.off);f.off+=int64(n);return n,e}\n if f.off >= f.node.dSize() {')
s=s.replace('if off >= f.node.dSize() {','if f.node.d!=nil {return f.node.d.readAt(p,off)}\n if off >= f.node.dSize() {')
s=s.replace('end := off + int64(len(p))','if f.node.d!=nil {n,e:=f.node.d.writeAt(p,off);if e!=nil{panic(e)};f.node.modTime=time.Now();return n}\n end := off + int64(len(p))')
save(n,s)
n='internal/prepared/entry.go';save(n,replace(read(n),'type Entry struct {','type Entry struct {\n Heap *Heap'))
n='internal/generatedgo/code/base/owned_prepared.go';s=read(n)
s=replace(s,'p := &PreparedFiles{}','if len(entries)==1 && entries[0].Heap!=nil {return MapHeap(fsys,entries[0].Heap,prefix)}\n p := &PreparedFiles{}')
s=replace(s,'var data []byte','var data []byte\n prot:=syscall.PROT_READ|syscall.PROT_WRITE\n if fsys.dEnabled {prot=syscall.PROT_READ}')
s=replace(s,'syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE','prot, syscall.MAP_PRIVATE')
s=replace(s,'node.data = data','if fsys.dEnabled {node.d=newDStorage(data);node.data=nil}else{node.data=data}');save(n,s)
n='internal/generatedgo/runtime_instance.go';s=read(n)
s=replace(s,'fs := base.NewMemFS()','fs := base.NewMemFS()\n fs.DEnable(restore!=nil)')
s=replace(s,'\t\tif transfer != "" {','\t\tif request:=prepared.FindHeap(transfer);request!=nil {request.Result,err=fs.FreezeHeap(GuestSHA256,request.Audit);return}\n\t\tif transfer != "" {');save(n,s)
n='internal/generatedgo/main.go';s=read(n)
s=replace(s,'ctx, finishTiming := timing.Begin(context.Background(), "snapshot_export")','if os.Getenv("MARIAMEM_HEAP")=="1" {return fmt.Errorf("heap experiment attempted file export")}\n ctx, finishTiming := timing.Begin(context.Background(), "snapshot_export")');save(n,s)
n='internal/snapshot/owned.go';s=read(n)
s=replace(s,'type Owned struct {','type Owned struct {\n heap *prepared.Heap')
a='\tif e := checkManifest(o.manifest, build); e != nil {\n\t\treturn fail(e)\n\t}'
s=replace(s,a,a+'\n if o.heap!=nil {if e:=o.heap.Check(build);e!=nil{return fail(e)};return []prepared.Entry{{Heap:o.heap}},o.mu.RUnlock,nil}')
s=replace(s,'o.closed = true','o.closed = true\n o.heap=nil');save(n,s)
n='snapshot.go';s=read(n)
s=replace(s,'saved := &Snapshot{opts: db.opts}','if opts.Destination=="" && os.Getenv("MARIAMEM_HEAP")=="1" {return db.snapshotHeap(ctx,opts)}\n saved := &Snapshot{opts: db.opts}');save(n,s)
# Reuse tested block and FS integration fixtures, retaining their source identity.
prior=ROOT/'benchmarks/spikes/d2-guest'
block=(prior/'block.go.txt').read_text();block=replace(block,'"math"','"math"\n "github.com/masahitojp/mariamem/internal/prepared"')
block=replace(block,'type dStorage struct {','type dStorage struct {\n inherited []prepared.HeapBlock')
a='   end:=at+n;if end>d.backingLimit{end=d.backingLimit}\n   if end>at {copy(out,d.backing[at:end]);clear(out[end-at:])} else {clear(out)}'
block=replace(block,a,'   d.original(out,at)');block=replace(block,'copy(b,d.backing[begin:limit])','d.original(b[:limit-begin],begin)')
new={'internal/generatedgo/code/base/d_block.go':block}
for src,dst in [('block_test.go.txt','d_block_test.go'),('integration_test.go.txt','d_integration_test.go')]:new['internal/generatedgo/code/base/'+dst]=(prior/src).read_text()
for src,dst in [('heap.go.txt','internal/prepared/heap.go'),('heap_base.go.txt','internal/generatedgo/code/base/heap.go'),('heap_owned.go.txt','internal/snapshot/heap.go'),('heap_host.go.txt','internal/host/heap.go'),('heap_public.go.txt','heap_experiment.go'),('heap_test.go.txt','internal/generatedgo/code/base/heap_test.go')]:new[dst]=(HERE/src).read_text()
for n,s in new.items():assert not (ROOT/n).exists(),n;changes[n]={'before':None};save(n,s)
subprocess.run([os.environ['GOFMT'],'-w',*[str(ROOT/n) for n in changes]],check=True)
for n,d in changes.items():d['after']=hashlib.sha256((ROOT/n).read_bytes()).hexdigest()
(HERE/'instrumentation.json').write_text(json.dumps(changes,indent=2)+'\n')
