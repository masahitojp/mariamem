"""Observation only: retain the static-image prototype's lock and ownership scope."""
from pathlib import Path
import hashlib, json, runpy, sys
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:])
runpy.run_path(str(s/'benchmarks/undorelay/overlay.py'),run_name='__main__')
maps=json.loads((o/'overlay.json').read_text());hashes=json.loads((o/'hashes.json').read_text())
def patch(rel, edits):
 p=s/rel; prior=Path(maps['Replace'].get(str(p),p));old=prior.read_text();v=old
 for a,b in edits:
  assert v.count(a)==1,(rel,a,v.count(a));v=v.replace(a,b)
 out=o/('stages-'+p.name);out.write_text(v);maps['Replace'][str(p)]=str(out)
 hashes.append({'path':rel,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
patch('benchmarks/staticimage/image.go',[
 ('func (f *factory) acquire() (*child, error) {\n\tf.mu.Lock()', '''func (f *factory) acquire() (*child, error) { return f.acquireObserved(func(string){}) }
func (f *factory) acquireObserved(mark func(string)) (*child, error) {
 mark("runtime/image_lock_begin")
 f.mu.Lock()
 mark("runtime/image_lock_acquired")'''),
 ('\t\tf.buildErr = f.build()', '\t\tmark("runtime/image_build_begin")\n\t\tf.buildErr = f.build()\n\t\tmark("runtime/image_build_end")'),
 ('\tb, err := f.mapImage(', '\tmark("runtime/map_begin")\n\tb, err := f.mapImage('),
 ('\ttransferred := false', '\tmark("runtime/map_end")\n\ttransferred := false'),
 ('\tm := generated.NewFromSnapshot(', '\tmark("runtime/module_begin")\n\tm := generated.NewFromSnapshot('),
 ('\tm.PrepareMemoryGrow = b.Grow', '\tm.PrepareMemoryGrow = b.Grow\n\tmark("runtime/module_end")'),
 ('\tc, e := f.acquire()', '''return f.AcquireForHostObserved(wasi, wasix,func(string){})
}
func (f *factory) AcquireForHostObserved(wasi base.Wasi_snapshot_preview1Imports, wasix base.Wasix_32v1Imports,mark func(string)) (*base.Module,func()error,error) {
 c,e := f.acquireObserved(mark)''')])
patch('internal/generatedgo/memory_backing_unix.go',[
 (''' timing.Mark(ctx,"runtime/construct_begin");m,release,err=newMemoryModule(h);timing.Mark(ctx,"runtime/construct_end");return''','''
 mark:=func(name string){timing.Mark(ctx,name)}
 mark("runtime/memory_begin")
 defer mark("runtime/memory_ready")
 if staticImageEnabled {
  m,release,err=experimentImage.AcquireForHostObserved(h,h,mark)
  if err==nil {installGuestThreadLifetime(m)}
  return
 }
 return initializeMemoryModule(func()(*base.MemoryMapping,error){
  mark("runtime/map_begin")
  b,e:=base.NewMemoryMapping(generated.InitialMemoryBytes,2<<30)
  mark("runtime/map_end")
  return b,e
 },func(b *base.MemoryMapping)*base.Module{
  mark("runtime/module_begin")
  m:=generated.NewWithMemory(h,nil,h,b.Bytes(),generated.InitialMemoryBytes)
  mark("runtime/module_end")
  installGuestThreadLifetime(m)
  return m
 })''')])
patch('benchmarks/staticimageruntime/probe/probe.go',[
 ('"context"','"context"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('type Sample struct {','type Sample struct {\n Traces map[string]timing.Trace `json:"traces,omitempty"`'),
 ('\tvar d *Database\n\tvar p *sql.DB', '''s.Traces=make(map[string]timing.Trace)
 ctx=timing.WithRecorder(ctx,func(tr timing.Trace){s.Traces[tr.Operation]=tr})
 var d *Database
 var p *sql.DB''')])
patch('internal/timing/timing.go',[
 ('var sequence atomic.Uint64','var sequence atomic.Uint64\nvar stagesEpoch = time.Now()'),
 ('type Trace struct {','type Trace struct {\n EpochNS int64 `json:"epoch_ns"`'),
 ('ctx = context.WithValue(ctx, key{}, t)','t.EpochNS=t.start.Sub(stagesEpoch).Nanoseconds()\nctx = context.WithValue(ctx, key{}, t)')])
(o/'overlay.json').write_text(json.dumps(maps,indent=2)+'\n')
(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
