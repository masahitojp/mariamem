from pathlib import Path
import json
w=Path.cwd();src=w/'worktree';tmp=w/'temp';mapping={}
def edit(rel,pairs):
    p=src/rel;s=p.read_text()
    for a,b in pairs:
        assert s.count(a)==1,(rel,a)
        s=s.replace(a,b)
    out=tmp/p.name;out.write_text(s);mapping[str(p)]=str(out)
edit('internal/timing/timing.go',[
 ('dir        string','guestReader func() ([]byte,error)\n dir string'),
 ('// ReadGuest copies','''func BindGuestReader(ctx context.Context, reader func()([]byte,error)) {
    if t,ok:=ctx.Value(key{}).(*Trace);ok { t.mu.Lock();t.guestReader=reader;t.mu.Unlock() }
}
// ReadGuest copies'''),
 ('data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))','''t.mu.Lock();reader:=t.guestReader;t.mu.Unlock()
 var data []byte
 var err error
 if reader!=nil {data,err=reader()} else {data,err=os.ReadFile(filepath.Join(transfer,"startup-timing.json"))}''')])
edit('internal/guest/linked.go',[('generatedgo.StartInstanceWithStopped(childIn,','generatedgo.StartInstanceObserved(ctx, childIn,')])
edit('internal/generatedgo/runtime_instance.go',[
 ('"errors"','"errors"\n"context"\n"os"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('var libraryMode sync.Once','''var libraryMode sync.Once
func StartInstanceObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),captures ...*prepared.Capture)(<-chan error,<-chan error){
    stopped:=make(chan error,1)
    done:=runObserved(ctx,in,out,stderr,transfer,restore,guestTiming,onFailure,newMemoryModule,func(err error){stopped<-err},generated.Start,captures...)
    return stopped,done
}'''),
 ('\t// CLI diagnostic entrypoints','''return runObserved(context.Background(),in,out,stderr,transfer,restore,guestTiming,onFailure,construct,onStopped,start,captures...)
}
func runObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),construct func(*host)(*base.Module,func()error,error),onStopped func(error),start func(*base.Module),captures ...*prepared.Capture)<-chan error{
 // CLI diagnostic entrypoints'''),
 ('\t\tvar maps *base.PreparedFiles','''if guestTiming && os.Getenv("FORK_GUEST_CLOCK")=="1" {
     timing.BindGuestReader(ctx,func()([]byte,error){
         f,err:=fs.OpenFile("snapshot-out/startup-timing.json",0,0)
         if err!=nil{return nil,err};defer f.Close()
         return io.ReadAll(io.LimitReader(f,128*1024+1))
     })
 }
 timing.Mark(ctx,"runtime/maps_begin")
 var maps *base.PreparedFiles'''),
 ('created, ownedRelease, allocErr := construct(h)','''timing.Mark(ctx,"runtime/module_begin")
 created, ownedRelease, allocErr := construct(h)
 timing.Mark(ctx,"runtime/module_ready")'''),
 ('if err = executeGuest(m, start);','timing.Mark(ctx,"runtime/execute_begin")\n if err = executeGuest(m, start);')])
(tmp/'overlay.json').write_text(json.dumps({'Replace':mapping}))
