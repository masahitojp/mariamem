import json,hashlib,sys
from pathlib import Path
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);o.mkdir(parents=True,exist_ok=True);repl={};hashes=[]
def patch(path,edits):
 original=(s/path).read_text();v=original
 for before,after in edits:
  assert v.count(before)==1,(path,before);v=v.replace(before,after)
 p=o/Path(path).name;p.write_text(v);repl[str(s/path)]=str(p);hashes.append({'path':path,'before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
patch('internal/timing/timing.go',[
 ('dir        string','guestReader func() ([]byte,error)\n\tdir        string'),
 ('// ReadGuest copies','''func BindGuestReader(ctx context.Context, reader func() ([]byte,error)) { if t,ok:=ctx.Value(key{}).(*Trace);ok { t.mu.Lock();t.guestReader=reader;t.mu.Unlock() } }
// ReadGuest copies'''),
 ('data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))','''t.mu.Lock();reader:=t.guestReader;t.mu.Unlock()
        var data []byte;var err error
        if reader != nil { data,err=reader() } else { data,err=os.ReadFile(filepath.Join(transfer,"startup-timing.json")) }''')])
patch('internal/guest/linked.go',[
 ('generatedgo.StartInstance(childIn,','generatedgo.StartInstanceObserved(ctx, childIn,')])
patch('internal/generatedgo/runtime_instance.go',[
 ('"errors"','"errors"\n"context"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('var libraryMode sync.Once','''var libraryMode sync.Once
func StartInstanceObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),captures ...*prepared.Capture) <-chan error {
 return startObservedInstance(ctx,in,out,stderr,transfer,restore,guestTiming,onFailure,func(h *host)(*base.Module,func()error,error){ return newObservedMemoryModule(h,ctx) },captures...)
}'''),
 ('\t// CLI diagnostic entrypoints',''' return startObservedInstance(context.Background(),in,out,stderr,transfer,restore,guestTiming,onFailure,construct,captures...)
}
func startObservedInstance(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),construct func(*host)(*base.Module,func()error,error),captures ...*prepared.Capture) <-chan error {
 // CLI diagnostic entrypoints'''),
 ('go func() {\n\t\tvar err error','go func() {\n timing.Mark(ctx,"runtime/instance_begin")\n\t\tvar err error'),
 ('\t\tvar maps *base.PreparedFiles','''if guestTiming { timing.BindGuestReader(ctx,func()([]byte,error){ f,e:=fs.OpenFile("snapshot-out/startup-timing.json",0,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(io.LimitReader(f,128*1024+1)) }) }
        timing.Mark(ctx,"runtime/prepared_handles_begin")
        var maps *base.PreparedFiles'''),
 ('\t\th := &host{','timing.Mark(ctx,"runtime/prepared_handles_ready")\n\t\th := &host{'),
 ('\t\tif err = executeGuest(m, generated.Start);','timing.Mark(ctx,"runtime/guest_execute_begin")\n\t\tif err = executeGuest(m, generated.Start);')])
patch('internal/generatedgo/memory_backing_unix.go',[
 ('"errors"','"errors"\n"context"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('// Constructor ownership','''func newObservedMemoryModule(h *host,ctx context.Context)(m *base.Module,release func()error,err error) {
 timing.Mark(ctx,"runtime/construct_begin");m,release,err=newMemoryModule(h);timing.Mark(ctx,"runtime/construct_end");return
}
// Constructor ownership''')])
(o/'overlay.json').write_text(json.dumps({'Replace':repl},indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
