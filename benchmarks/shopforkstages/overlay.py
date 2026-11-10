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
func SetCommonTimer(ctx context.Context, values []uint64) {
 if t,ok:=ctx.Value(key{}).(*Trace);ok {t.mu.Lock();t.CommonTimer=values;t.mu.Unlock()}
}
var sequence atomic.Uint64''' ),
 ('\tdir        string','\tCommonTimer []uint64 `json:"common_timer,omitempty"`\n\tguestReader func() ([]byte,error)\n\tdir        string'),
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
 ('import (','import (\n"context"\n"encoding/binary"\n"github.com/masahitojp/mariamem/internal/timing"'),(old,new),
 ('go func() {\n\t\tvar err error','go func() {\n timing.Mark(ctx,"instance_begin")\n\t\tvar err error'),
 ('\t\tw := base.DefaultWASI()','\t\ttiming.Mark(ctx,"filesystem_begin")\n\t\tw := base.DefaultWASI()'),
 ('\t\th := &host{','''  timing.Mark(ctx,"filesystem_ready")
  if guestTiming {timing.AttachGuestReader(ctx,func()([]byte,error){
   f,e:=fs.OpenFile("snapshot-out/startup-timing.json",0,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(io.LimitReader(f,128*1024+1))
  })}
\t\th := &host{'''),
 ('\t\tm, release, allocErr := construct(h)','\t\ttiming.Mark(ctx,"memory_begin")\n\t\tm, release, allocErr := construct(h)\n\t\ttiming.Mark(ctx,"memory_ready")'),
 ('\t\tif err = executeGuest(m, generated.Start);','\t\tif timing.Enabled(ctx) { m.CommonMark = func(name string) {\n timing.Mark(ctx,"common_"+name)\n if name=="timer_end" { values:=make([]uint64,20);for i:=range values {values[i]=binary.LittleEndian.Uint64(m.Memory[26639680+i*8:26639688+i*8])};timing.SetCommonTimer(ctx,values) }\n if name=="end" {m.CommonMark=nil}\n } }\n\t\ttiming.Mark(ctx,"execute_begin")\n\t\tif err = executeGuest(m, generated.Start);'),
 ('values = append(values, "MARIAMEM_GUEST_TIMING=1")','values = append(values, "MARIAMEM_GUEST_TIMING=1", "MARIAMEM_INIT_DIAGNOSTICS=1")')])
patch('internal/guest/linked.go',[('generatedgo.StartInstance(childIn,','generatedgo.StartObservedInstance(ctx,childIn,')])
unit=H/'observer_unit.go.txt';maps[str(S/'internal/timing/fork_observer_test.go')]=str(unit)
hashes.append(dict(path='internal/timing/fork_observer_test.go',before_sha256=None,after_sha256=hashlib.sha256(unit.read_bytes()).hexdigest()))
(O/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n');(O/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
# Compiler-inlined startup blocks: bind complete instruction bodies, not a
# historical function number or a guessed source line. Insert observation only.
import re
symbol_path=S.parent/'temp/function-map.txt'
assert hashlib.sha256(symbol_path.read_bytes()).hexdigest()==plan['symbol_map_sha256']
names=dict(line.split(':',1) for line in symbol_path.read_text().splitlines())
assert names['5573']=='init_embedded_server' and names['961']=='init_available_charsets'
assert names['70']=='strlen' and names['808']=='my_hash_init2' and names['814']=='my_hash_insert'
patch('internal/generatedgo/code/base/base.go',[
 ('type Module struct {','type Module struct {\nCommonMark func(string) // experiment-only per-instance observer')])
name='internal/generatedgo/code/p0/p0_pure.go';original=(S/name).read_text()
assert hashlib.sha256(original.encode()).hexdigest()==plan['overlay_preimages'][name]
start=original.index('func Fn5573(');end=original.index('\nfunc ',start+1)
body=original[start:end]
# Each anchor is unique within this exact body. Labels are control-flow entry
# points; the timer continuation is not a contiguous physical source range.
anchors=[
 ('begin','\tFn227(m, int32(8563877))'),
 ('timer_begin','L64:\n\t;\n\tv735 = int32(0)'),
 ('timer_end','L1466:\n\t;\n\tm.G0 = v739 + int32(32)'),
 ('locale_begin','\tv9783 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, 17844288, 0, 4)))'),
 ('locale_end','L1855:\n\t;\n\tv10632 ='),
 ('lex_begin','L2770:\n\t;\n\tv14809 ='),
 ('lex_end','L2775:\n\t;\n\tv14950 ='),
 ('functions_begin','L2775:\n\t;\n\tv14950 ='),
 ('functions_end','L2828:\n\t;\n\t*(*int32)'),
 ('json_begin','\tv15815 = int32(0)'),
 ('json_end','L2833:\n\t;\n\tv15957 ='),
 ('end','\tFn227(m, int32(8620041))'),
]
modified=body;insertions=[];bindings=[];positions={}
for event,anchor in anchors:
 assert body.count(anchor)==1,(event,body.count(anchor))
 offset=anchor.index('\n\t;\n')+5 if anchor.startswith('L') else 0
 at=body.index(anchor)+offset
 injected='\tif m.CommonMark != nil { m.CommonMark("'+event+'") }\n'
 positions.setdefault(at,[]).append(injected)
 insertions.append(injected)
 bindings.append(dict(event=event,anchor=anchor,body_line=body[:at].count('\n')+1))
for at,parts in sorted(positions.items(),reverse=True):
 modified=modified[:at]+''.join(parts)+modified[at:]
# All original guest operations and branches must remain byte-identical.
restored=modified
for inserted in insertions:restored=restored.replace(inserted,'',1)
assert restored==body
result=original[:start]+modified+original[end:]
dst=O/'common-p0.go';dst.write_text(result)
subprocess.run(['/opt/homebrew/bin/gofmt','-w',str(dst)],check=True)
maps[str(S/name)]=str(dst);hashes.append(dict(path=name,before_sha256=hashlib.sha256(original.encode()).hexdigest(),after_sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
# Charset initialization may be outside the common span. Keep it as a nested
# observation and never blindly add it to the common partition.
for file in (S/'internal/generatedgo/code').glob('p*/p*_pure.go'):
 source=file.read_text();match=re.search(r'^func Fn961\([^\n]+\{\n',source,re.M)
 if not match:continue
 start=match.start();end=source.index('\nfunc ',start+1);block=source[start:end]
 inject='\tif cb := m.CommonMark; cb != nil { cb("charset_begin"); defer cb("charset_end") }\n'
 patched=source[:match.end()]+inject+source[match.end():]
 assert patched.replace(inject,'',1)==source
 target=O/'common-charset.go';target.write_text(patched)
 subprocess.run(['/opt/homebrew/bin/gofmt','-w',str(target)],check=True)
 maps[str(file)]=str(target);hashes.append(dict(path=str(file.relative_to(S)),before_sha256=hashlib.sha256(source.encode()).hexdigest(),after_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
 break
else:raise AssertionError('missing charset function')
(O/'bindings.json').write_text(json.dumps(dict(guest_sha256=json.loads((S/'internal/generatedgo/provenance.json').read_text())['guest_sha256'],symbol_map_sha256=plan['symbol_map_sha256'],function='5573:init_embedded_server',function_body_sha256=hashlib.sha256(body.encode()).hexdigest(),original_instruction_bytes_preserved=True,anchors=bindings,charset_function='961:init_available_charsets'),indent=2)+'\n')
(O/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n')
(O/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
