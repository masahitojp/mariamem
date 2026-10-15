"""Apply exact-baseline experimental overlays; restore before saving results."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
subprocess.run(["python3",str(HERE/'instrument_base.py')],check=True)
changes=json.loads((HERE/'instrumentation.json').read_text())
def change(name,fun):
    p=ROOT/name
    if name not in changes:changes[name]={'before':hashlib.sha256(p.read_bytes()).hexdigest()}
    p.write_text(fun(p.read_text()))
def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)

change('internal/prepared/entry.go',lambda s:replace(s,'type Entry struct {','type Entry struct {\n D2 *D2Layout'))
change('internal/generatedgo/code/base/base.go',lambda s:replace(s,'type MemFS struct {','type MemFS struct {\n d2 *d2Pool'))
change('internal/generatedgo/code/base/d_integration.go',lambda s:s.replace('n.d = newDStorage(nil)','n.d = newDStorage(nil)\n n.d.pool=fsys.d2'))
def block(s):
    s=s.replace('"math"','"math"\n "github.com/masahitojp/mariamem/internal/prepared"')
    s=replace(s,'type dStorage struct {','type dStorage struct {\n pool *d2Pool\n inherited []prepared.D2Ref\n refs map[int64]prepared.D2Ref')
    s=s.replace('blocks: make(map[int64][]byte)', 'blocks: make(map[int64][]byte),refs:make(map[int64]prepared.D2Ref)')
    a=s.index('\t\t\tend := at + n');b=s.index('\n\t\t}',a)
    s=s[:a]+'\t\t\td.original(out,at)'+s[b:]
    s=s.replace('b = make([]byte, dBlockSize)','if d.pool==nil { b=make([]byte,dBlockSize) } else { var ref prepared.D2Ref; var err error; b,ref,err=d.pool.alloc();if err!=nil{return int(done),err};d.refs[index]=ref }')
    s=s.replace('copy(b, d.backing[begin:limit])','d.original(b[:limit-begin],begin)')
    return s
change('internal/generatedgo/code/base/d_block.go',block)
change('internal/generatedgo/code/base/owned_prepared.go',lambda s:replace(s,'p := &PreparedFiles{}','if len(entries)==1 && entries[0].D2!=nil {return MapD2Handles(fsys,entries[0].D2,prefix)}\n p := &PreparedFiles{}'))
def runtime(s):
    s=s.replace('"io"','"io"\n "os"')
    s=replace(s,'fs.DEnable(restore != nil)','fs.DEnable(restore != nil)\n if err=fs.D2Enable();err!=nil{return}\n defer func(){err=errors.Join(err,fs.D2Close())}()')
    s=s.replace('if restore == nil {','if restore == nil && os.Getenv("MARIAMEM_D2")!="1" {')
    s=s.replace('if handled, e := fs.EHandoff(', 'if handled,e:=fs.D2Handoff(transfer,GuestSHA256);handled{err=e;return}\n if handled, e := fs.EHandoff(')
    return s
change('internal/generatedgo/runtime_instance.go',runtime)
def owned(s):
    s=replace(s,'type Owned struct {','type Owned struct {\n d2 *prepared.D2Layout')
    s=replace(s,'type Handoff struct {','type Handoff struct {\n D2 *prepared.D2Layout `json:"d2,omitempty"`')
    s=replace(s,'func ReceiveInherited(h Handoff, build string) (result *Owned, err error) {','func ReceiveInherited(h Handoff, build string) (result *Owned, err error) {\n if h.D2!=nil {return ReceiveD2(h,build)}')
    s=replace(s,'for _, v := range o.entries {','if o.d2!=nil {if e:=o.d2Metadata();e!=nil{return fail(e)};return []prepared.Entry{{D2:o.d2}},o.mu.RUnlock,nil}\n for _, v := range o.entries {')
    return s
change('internal/snapshot/owned.go',owned)
def server(s):
    s=replace(s,'type Server struct {','type Server struct {\n d2Direct bool')
    s=s.replace('eDirect: restore == nil && os.Getenv("MARIAMEM_E_MODE") == "handoff",','eDirect: restore == nil && os.Getenv("MARIAMEM_E_MODE") == "handoff" && os.Getenv("MARIAMEM_D2")!="1", d2Direct:os.Getenv("MARIAMEM_D2")=="1" && (restore==nil || restore.IsD2()),')
    sig='func (s *Server) Snapshot(ctx context.Context, destination string, rollback bool) (closed bool, err error) {'
    s=replace(s,sig,'func(s *Server) Snapshot(ctx context.Context,destination string,rollback bool)(bool,error){return s.snapshotInternal(ctx,destination,rollback,false)}\nfunc(s *Server) SnapshotBlocks(ctx context.Context,destination string,rollback bool)(bool,error){return s.snapshotInternal(ctx,destination,rollback,true)}\nfunc (s *Server) snapshotInternal(ctx context.Context,destination string,rollback,blocks bool)(closed bool,err error){\n directD2:=blocks && s.d2Direct')
    marker='timing.Mark(ctx, "preconditions_destination_ready")'
    s=replace(s,marker,marker+'\n if directD2 {if err=os.WriteFile(filepath.Join(s.transfer,".d2-request"),nil,0600);err!=nil{s.mu.Unlock();return false,err}}')
    s=s.replace('!s.eDirect || os.Getenv("MARIAMEM_E_AUDIT") == "1"','!(s.eDirect || directD2) || os.Getenv("MARIAMEM_E_AUDIT") == "1"')
    s=replace(s,'if s.eDirect {\n\t\terr = snapshot.PublishSharedExperimental', 'if directD2 {err=snapshot.PublishD2(s.transfer,path)} else if s.eDirect {\n\t\terr = snapshot.PublishSharedExperimental')
    return s
change('internal/host/server.go',server)
def main(s):
    s=replace(s,'type request struct {','type request struct {\n D2 bool `json:"d2"`')
    s=s.replace('io.LimitReader(f, 1<<20)','io.LimitReader(f, 16<<20)')
    s=replace(s,'accepted, e := s.Snapshot(ctx, msg.req.Destination, msg.req.Rollback)','var accepted bool;var e error\n if msg.req.D2 {accepted,e=s.SnapshotBlocks(ctx,msg.req.Destination,msg.req.Rollback)} else {accepted,e=s.Snapshot(ctx,msg.req.Destination,msg.req.Rollback)}')
    return s
change('cmd/mariamem-host/main.go',main)
for src,dst in [('layout.go.txt','internal/prepared/d2.go'),('pool.go.txt','internal/generatedgo/code/base/d2_pool.go'),('d2_handoff.go.txt','internal/generatedgo/code/base/d2_handoff.go'),('d2_owned.go.txt','internal/snapshot/d2_owned.go'),('d2_test.go.txt','internal/generatedgo/code/base/d2_test.go')]:
    assert not (ROOT/dst).exists();changes[dst]={'before':None};(ROOT/dst).write_bytes((HERE/src).read_bytes())
p=ROOT/'internal/snapshot/d2_owned.go';p.write_text(p.read_text()+'\nfunc(o *Owned) IsD2()bool{return o!=nil && o.d2!=nil}\n')
subprocess.run([os.environ['GOFMT'],'-w',*[str(ROOT/n) for n in changes]],check=True)
for name,v in changes.items():v['after']=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
(HERE/'instrumentation.json').write_text(json.dumps(changes,indent=2)+'\n')
