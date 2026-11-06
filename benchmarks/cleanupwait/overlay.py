from pathlib import Path
import sys,json,hashlib,subprocess
s,o=[Path(x).resolve() for x in sys.argv[1:]];o.mkdir(parents=True,exist_ok=True);repl={};hashes=[]
def patch(n,edits):
 a=(s/n).read_text();b=a
 for x,y in edits:
  assert b.count(x)==1,(n,x);b=b.replace(x,y)
 p=o/Path(n).name;p.write_text(b);subprocess.run(['gofmt','-w',str(p)],check=True)
 repl[str(s/n)]=str(p);hashes.append({'path':n,'before_sha256':hashlib.sha256(a.encode()).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
patch('internal/host/server.go',[
 ('type Server struct {','var issue117Trace = os.Getenv("ISSUE117_TRACE")=="1"\n\ntype Server struct {\n issue117Idle time.Time'),
 ('func (s *Server) Capacity() int','func (s *Server) Issue117Idle() time.Time {s.mu.Lock();defer s.mu.Unlock();return s.issue117Idle}\nfunc (s *Server) Capacity() int'),
 ('s.clients[conn] = state','s.clients[conn] = state\n if issue117Trace {s.issue117Idle=time.Time{}}'),
 ('delete(s.clients, conn)','delete(s.clients, conn)\n if issue117Trace && len(s.clients)==0 {s.issue117Idle=time.Now()}')])
patch('mariamem.go',[
 ('func (db *Database) WaitDisconnected(ctx context.Context) error {','''func (db *Database) WaitDisconnected(ctx context.Context) error {
 record,_:=ctx.Value("issue117_wait_record").(func(map[string]any))
 var started time.Time;var checks []map[string]any; sleeps:=0;success:=false;var idle time.Time
 if record!=nil {started=time.Now();defer func(){
  v:=map[string]any{"checks":checks,"sleep_requests":sleeps,"success":success,"elapsed_ms":float64(time.Since(started))/1e6,"idle_observed":!idle.IsZero()}
  if !idle.IsZero(){v["idle_offset_ms"]=float64(idle.Sub(started))/1e6;v["idle_to_observe_ms"]=float64(time.Since(idle))/1e6}
  record(v)
 }()}
'''),
 ('\t\tactive := db.server.Active()','''\t\tactive := db.server.Active()
 if record!=nil {
  checks=append(checks,map[string]any{"active":active,"offset_ms":float64(time.Since(started))/1e6})
  if active==0 {if observer,ok:=db.server.(interface{Issue117Idle() time.Time});ok {idle=observer.Issue117Idle()}}
 }'''),
 ('\t\tif active == 0 {\n\t\t\treturn nil','\t\tif active == 0 {\n success=true\n\t\t\treturn nil'),
 ('\t\tcase <-time.After(5 * time.Millisecond):','\t\tcase <-time.After(5 * time.Millisecond):\n if record!=nil {sleeps++}')])
p=o/'issue117_test.go';p.write_bytes((s/'benchmarks/cleanupwait/observer-test.go.txt').read_bytes());repl[str(s/'issue117_test.go')]=str(p)
(o/'overlay.json').write_text(json.dumps({'Replace':repl},indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
