from pathlib import Path
import sys,runpy,json,hashlib,subprocess
s,o=[Path(x).resolve() for x in sys.argv[1:]];o.mkdir(parents=True,exist_ok=True)
original_argv=sys.argv[:];sys.argv=[original_argv[0],str(s),str(o/'wait')];runpy.run_path(str(s/'benchmarks/cleanupwait/overlay.py'),run_name='__main__')
wait=json.loads((o/'wait/overlay.json').read_text())['Replace']
sys.argv=[original_argv[0],str(s),str(o/'undo')];runpy.run_path(str(s/'benchmarks/undorelay/overlay.py'),run_name='__main__');sys.argv=original_argv
maps=json.loads((o/'undo/overlay.json').read_text())['Replace'];assert not set(maps)&set(wait);maps.update(wait)
def patch(rel,edits):
 orig=(s/rel).read_text();v=Path(maps[str(s/rel)]).read_text() if str(s/rel) in maps else orig
 for before,after in edits:
  assert v.count(before)==1,(rel,before,v.count(before));v=v.replace(before,after)
 out=o/('notify-'+Path(rel).name);out.write_text(v);subprocess.run(['gofmt','-w',str(out)],check=True);maps[str(s/rel)]=str(out)
patch('internal/guest/guest.go',[
 ('\tfailure            error','\tfailure            error\n failureDone chan struct{}'),
 ('// Err reports','''// FailureDone is closed when failure is first recorded, independently of joined disposal.
func(p *Process) FailureDone() <-chan struct{} {
 p.mu.Lock();defer p.mu.Unlock()
 if p.failureDone==nil {p.failureDone=make(chan struct{});if p.failure!=nil {close(p.failureDone)}}
 return p.failureDone
}
// Err reports'''),
 ('\t\tp.failure = err','\t\tp.failure = err\n if p.failureDone!=nil {close(p.failureDone)}')])
patch('internal/host/server.go',[
 ('\tissue117Idle time.Time','\tissue117Idle time.Time\n disconnectChanged chan struct{}'),
 ('func (s *Server) Capacity() int','''// DisconnectState checks count and registers a generation under one lock.
func(s *Server) DisconnectState()(int,<-chan struct{},<-chan struct{},<-chan struct{}){
 s.mu.Lock();defer s.mu.Unlock()
 if s.disconnectChanged==nil {s.disconnectChanged=make(chan struct{})}
 return len(s.clients),s.disconnectChanged,s.Guest.FailureDone(),s.Guest.Done()
}
func(s *Server) disconnectChangedLocked(){
 if s.disconnectChanged!=nil {close(s.disconnectChanged);s.disconnectChanged=nil}
}
func (s *Server) Capacity() int'''),
 ('\t\t\ts.slots[state.slot] = false','\t\t\ts.slots[state.slot] = false\n s.disconnectChangedLocked()'),
 ('\ts.closing = true','\ts.closing = true\n s.disconnectChangedLocked()')])
patch('mariamem.go',[
 ('// Options configures','var issue117Notify = os.Getenv("ISSUE117_VARIANT")=="notify"\n\n// Options configures'),
 ('\t\tactive := db.server.Active()','''var active int
 var changed,failed,done <-chan struct{}
 if observer,ok:=db.server.(interface{DisconnectState()(int,<-chan struct{},<-chan struct{},<-chan struct{})});ok && issue117Notify {
  active,changed,failed,done=observer.DisconnectState()
 }else{active=db.server.Active()}'''),
 ('\t\tselect {\n\t\tcase <-ctx.Done():\n\t\t\treturn ctx.Err()\n\t\tcase <-time.After(5 * time.Millisecond):','''if changed!=nil {
 select {case <-ctx.Done():return ctx.Err();case <-changed:case <-failed:case <-done:}
 continue
 }
\t\tselect {
\t\tcase <-ctx.Done():
\t\t\treturn ctx.Err()
\t\tcase <-time.After(5 * time.Millisecond):''')])
for rel,src in [('issue117_notify_test.go','root-test.go.txt'),('internal/host/issue117_notify_test.go','host-test.go.txt'),('internal/guest/issue117_notify_test.go','guest-test.go.txt')]:maps[str(s/rel)]=str(s/'benchmarks/cleanupnotify'/src)
hashes=[]
for target,source in sorted(maps.items()):
 p=Path(target);hashes.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'after_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
