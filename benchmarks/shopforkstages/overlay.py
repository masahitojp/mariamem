"""Opt-in, context-bound host timings and read-only guest diagnostic extraction."""
from pathlib import Path
import hashlib,json,subprocess,sys
S,O=[Path(x).resolve() for x in sys.argv[1:]];O.mkdir(parents=True,exist_ok=True)
H=Path(__file__).resolve().parent;plan=json.loads((H/'plan.json').read_text());maps={};hashes=[]
def patch(name,edits):
 p=S/name;v=p.read_text();old=v;assert hashlib.sha256(p.read_bytes()).hexdigest()==plan['overlay_preimages'][name]
 for a,b in edits:
  assert v.count(a)==1,(name,a,v.count(a));v=v.replace(a,b)
 out=O/p.name;out.write_text(v);subprocess.run(['/opt/homebrew/bin/gofmt','-w',str(out)],check=True)
 maps[str(p)]=str(out);hashes.append(dict(path=name,before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
patch('internal/timing/timing.go',[
 ('var sequence atomic.Uint64','''// Experiment-only reader is attached to the specific startup context.
func AttachGuestReader(ctx context.Context, reader func() ([]byte,error)) {
 if t,ok:=ctx.Value(key{}).(*Trace);ok {t.mu.Lock();t.guestReader=reader;t.mu.Unlock()}
}
var sequence atomic.Uint64'''),
 ('\tdir        string','\tguestReader func() ([]byte,error)\n\tdir        string'),
 ('\treturn ctx, func() {\n\t\tMark(ctx, "end")','''\treturn ctx, func() {
  t.mu.Lock();reader:=t.guestReader;t.guestReader=nil;t.mu.Unlock()
  if reader!=nil {
   Mark(ctx,"diagnostic_read_begin")
   if b,e:=reader();e==nil&&len(b)<=128*1024&&json.Valid(b){t.Guest=b}
   Mark(ctx,"diagnostic_read_end")
  }
\t\tMark(ctx, "end")''')])
old='func startInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), captures ...*prepared.Capture) <-chan error {'
new=old+'''
 return startInstanceContext(context.Background(),in,out,stderr,transfer,restore,guestTiming,onFailure,construct,captures...)
}
func StartObservedInstance(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),captures ...*prepared.Capture) <-chan error {
 return startInstanceContext(ctx,in,out,stderr,transfer,restore,guestTiming,onFailure,newMemoryModule,captures...)
}
'''+old.replace('startInstance(in','startInstanceContext(ctx context.Context,in')
patch('internal/generatedgo/runtime_instance.go',[
 ('import (','import (\n"context"\n"github.com/masahitojp/mariamem/internal/timing"'),(old,new),
 ('go func() {\n\t\tvar err error','go func() {\n timing.Mark(ctx,"instance_begin")\n\t\tvar err error'),
 ('\t\tw := base.DefaultWASI()','\t\ttiming.Mark(ctx,"filesystem_begin")\n\t\tw := base.DefaultWASI()'),
 ('\t\th := &host{','''  timing.Mark(ctx,"filesystem_ready")
  if guestTiming {timing.AttachGuestReader(ctx,func()([]byte,error){
   f,e:=fs.OpenFile("snapshot-out/startup-timing.json",0,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(io.LimitReader(f,128*1024+1))
  })}
\t\th := &host{'''),
 ('\t\tm, release, allocErr := construct(h)','\t\ttiming.Mark(ctx,"memory_begin")\n\t\tm, release, allocErr := construct(h)\n\t\ttiming.Mark(ctx,"memory_ready")'),
 ('\t\tif err = executeGuest(m, generated.Start);','\t\ttiming.Mark(ctx,"execute_begin")\n\t\tif err = executeGuest(m, generated.Start);'),
 ('values = append(values, "MARIAMEM_GUEST_TIMING=1")','values = append(values, "MARIAMEM_GUEST_TIMING=1", "MARIAMEM_INIT_DIAGNOSTICS=1")')])
patch('internal/guest/linked.go',[('generatedgo.StartInstance(childIn,','generatedgo.StartObservedInstance(ctx,childIn,')])
unit=H/'observer_unit.go.txt';maps[str(S/'internal/timing/fork_observer_test.go')]=str(unit)
hashes.append(dict(path='internal/timing/fork_observer_test.go',before_sha256=None,after_sha256=hashlib.sha256(unit.read_bytes()).hexdigest()))
(O/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n');(O/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
