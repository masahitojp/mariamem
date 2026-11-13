from pathlib import Path
import hashlib,json,subprocess,sys
S,G,O=map(lambda v:Path(v).resolve(),sys.argv[1:]);O.mkdir(parents=True,exist_ok=True);replacements={};hashes=[]
def patch(root,path,edits):
 original=(root/path).read_text();v=original
 for before,after in edits:
  assert v.count(before)==1,(path,before,v.count(before));v=v.replace(before,after)
 p=O/(('maria-' if root==S else 'pg-')+path.replace('/','-'));p.write_text(v)
 subprocess.run(['gofmt','-w',p],check=True)
 replacements[str(root/path)]=str(p);hashes.append({'product':'maria' if root==S else 'pgmem','path':path,'before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
patch(S,'internal/timing/timing.go',[
 ('dir        string','guestReader func() ([]byte,error)\n\tdir        string'),
 ('record(*t)','record(*t)\n return'),
 ('// ReadGuest copies','''func Detached(ctx context.Context) context.Context { bg:=context.Background(); if r,ok:=ctx.Value(recorderKey{}).(func(Trace));ok {return WithRecorder(bg,r)};return bg }
func BindGuestReader(ctx context.Context, reader func() ([]byte,error)) { if t,ok:=ctx.Value(key{}).(*Trace);ok { t.mu.Lock();t.guestReader=reader;t.mu.Unlock() } }
// ReadGuest copies'''),
 ('data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))','''t.mu.Lock();reader:=t.guestReader;t.mu.Unlock()
 var data []byte;var err error
 if reader!=nil {data,err=reader()} else {data,err=os.ReadFile(filepath.Join(transfer,"startup-timing.json"))}''')])
patch(S,'internal/guest/linked.go', [('generatedgo.StartInstance(childIn,','generatedgo.StartInstanceObserved(ctx, childIn,')])
patch(S,'internal/generatedgo/runtime_instance.go',[
 ('"errors"','"errors"\n"context"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('var libraryMode sync.Once','''var libraryMode sync.Once
func StartInstanceObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),captures ...*prepared.Capture) <-chan error {
 return startObservedInstance(ctx,in,out,stderr,transfer,restore,guestTiming,onFailure,func(h *host)(*base.Module,func()error,error){timing.Mark(ctx,"runtime/memory_begin");m,r,e:=newMemoryModule(h);timing.Mark(ctx,"runtime/memory_ready");return m,r,e},captures...)
}'''),
 ('\t// CLI diagnostic entrypoints','''return startObservedInstance(context.Background(),in,out,stderr,transfer,restore,guestTiming,onFailure,construct,captures...)
}
func startObservedInstance(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),construct func(*host)(*base.Module,func()error,error),captures ...*prepared.Capture) <-chan error {
 // CLI diagnostic entrypoints'''),
 ('go func() {\n\t\tvar err error','go func() {\n timing.Mark(ctx,"runtime/instance_begin")\n\t\tvar err error'),
 ('\t\tvar maps *base.PreparedFiles','''if guestTiming {timing.BindGuestReader(ctx,func()([]byte,error){f,e:=fs.OpenFile("snapshot-out/startup-timing.json",0,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(io.LimitReader(f,128*1024+1))})}
 timing.Mark(ctx,"runtime/prepared_handles_begin")
 var maps *base.PreparedFiles'''),
 ('defer func() { err = errors.Join(err, w.CloseDescriptors(), maps.Close()) }()', '''defer func() {c,finish:=timing.Begin(timing.Detached(ctx),"runtime_files_close");defer finish();e1:=w.CloseDescriptors();timing.Mark(c,"descriptors_closed");e2:=maps.Close();timing.Mark(c,"prepared_maps_closed");err=errors.Join(err,e1,e2)}()'''),
 ('\t\th := &host{','timing.Mark(ctx,"runtime/prepared_handles_ready")\n\t\th := &host{'),
 ('defer releaseMemoryModule(m, release, &err)','''defer func(){c,finish:=timing.Begin(timing.Detached(ctx),"runtime_memory_close");defer finish();releaseMemoryModule(m,func()error{timing.Mark(c,"release_begin");e:=release();timing.Mark(c,"release_end");return e},&err)}()'''),
 ('\t\tif err = executeGuest(m, generated.Start);','timing.Mark(ctx,"runtime/guest_execute_begin")\n\t\tif err = executeGuest(m, generated.Start, ctx);'),
 ('func executeGuest(m *base.Module, start func(*base.Module)) (err error) {','func executeGuest(m *base.Module, start func(*base.Module), observed ...context.Context) (err error) {'),
 ('\t\troot := recover()','''root := recover()
 ctx:=context.Background();if len(observed)>0 {ctx=timing.Detached(observed[0])};ctx,finish:=timing.Begin(ctx,"runtime_threads_close");defer finish()
 timing.Mark(ctx,"root_returned")'''),
 ('worker = m.Threads.WaitThreads()','worker = m.Threads.WaitThreads()\n timing.Mark(ctx,"workers_joined")')])
patch(S,'mariamem.go',[
 ('type Database struct {','type Database struct {\n observedContext context.Context'),
 ('db := &Database{opts: opts,','db := &Database{observedContext:timing.Detached(ctx),opts: opts,'),
 ('func (db *Database) closeLocked() error {','''func (db *Database) closeLocked() error {
 observed:=db.observedContext;if observed==nil {observed=context.Background()};observed,finish:=timing.Begin(observed,"api_close");defer finish()'''),
 ('context.WithTimeout(context.Background(), db.opts.ShutdownTimeout)','context.WithTimeout(observed, db.opts.ShutdownTimeout)'),
 ('\tdb.closeErr = hostError(errors.Join(err, db.removeTemporaryAfter(err), db.captureDebt), "close", true)','''timing.Mark(observed,"server_closed")
 db.closeErr = hostError(errors.Join(err, db.removeTemporaryAfter(err), db.captureDebt), "close", true)
 timing.Mark(observed,"temporary_removed")''')])
patch(S,'internal/host/server.go',[
 ('func (s *Server) Close(ctx context.Context) (err error) {\n\tdefer func() { err = s.disposeAfter(err) }()', '''func (s *Server) Close(ctx context.Context) (err error) {
 ctx,finish:=timing.Begin(ctx,"host_close");defer finish()
 defer func() {timing.Mark(ctx,"dispose_begin");err=s.disposeAfter(err);timing.Mark(ctx,"dispose_end")}()'''),
 ('\treturn s.finish(ctx, shutdownDiscard)','timing.Mark(ctx,"admission_stopped");return s.finish(ctx, shutdownDiscard)'),
 ('\t\tif purpose == shutdownExport {\n\t\t\ttiming.Mark(ctx, "sessions_drained")','\t\ttiming.Mark(ctx,"sessions_joined")\n\t\tif purpose == shutdownExport {\n\t\t\ttiming.Mark(ctx, "sessions_drained")'),
 ('err = s.setShutdownMode(ctx, purpose)','timing.Mark(ctx,"shutdown_mode_begin");err = s.setShutdownMode(ctx, purpose);timing.Mark(ctx,"shutdown_mode_end")'),
 ('err = s.Guest.Shutdown(ctx)','timing.Mark(ctx,"shutdown_begin");err = s.Guest.Shutdown(ctx);timing.Mark(ctx,"shutdown_returned")')])

(O/'overlay.json').write_text(json.dumps({'Replace':replacements},indent=2)+'\n');(O/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
