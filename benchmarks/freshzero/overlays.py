"""Generate bounded diagnostic overlays without editing product source."""
import hashlib,json

def replace_once(s,old,new):
 assert s.count(old)==1,(old[:100],s.count(old))
 return s.replace(old,new)

def make(c,t,b):
 originals={};replacements={}
 def put(rel,text,name):
  src=c/rel;dst=t/name;dst.write_text(text);originals[rel]=hashlib.sha256(src.read_bytes()).hexdigest();replacements[str(src)]=str(dst)
 base='internal/generatedgo/code/base/base.go'
 put(base,replace_once((c/base).read_text(),'type Module struct {','type Module struct {\n // Experiment: valid only during a fresh-owner constructor.\n FreshZeroInit bool'),'base.go')
 gen='internal/generatedgo/code/generated.go';s=(c/gen).read_text()
 signature='func NewWithMemory(wasi_snapshot_preview1 base.Wasi_snapshot_preview1Imports, env base.EnvImports, wasix_32v1 base.Wasix_32v1Imports, memory []byte, memSize uint64) *base.Module {'
 args='wasi_snapshot_preview1, env, wasix_32v1, memory, memSize'
 wrappers=signature+'\n return newWithMemory('+args+', false)\n}\n'
 wrappers+=signature.replace('NewWithMemory','NewWithFreshZeroMemory')+'\n return newWithMemory('+args+', true)\n}\n'
 internal=signature.replace('NewWithMemory','newWithMemory').replace('memSize uint64)','memSize uint64, freshZero bool)')
 start=s.index(signature);end=s.index('\nfunc NewFromSnapshot',start)
 part=s[start:end].replace(signature,wrappers+internal,1)
 part=replace_once(part,'\tm.Memory = memory','\tm.FreshZeroInit = freshZero\n\tm.Memory = memory')
 s=s[:start]+part+s[end:];put(gen,s,'generated.go')
 host='internal/generatedgo/memory_backing_unix.go';s=(c/host).read_text()
 old='return initializeMemoryModule(func() (*base.MemoryMapping, error) { return base.NewMemoryMapping(generated.InitialMemoryBytes, 2<<30) }, func(b *base.MemoryMapping) *base.Module {'
 new='''return initializeMemoryModule(func() (*base.MemoryMapping, error) {
 at:=freshZeroBegin()
 b,e:=base.NewMemoryMapping(generated.InitialMemoryBytes,2<<30)
 if e==nil {freshZeroEnd("reserve",at,b.Bytes()[:generated.InitialMemoryBytes],nil)}
 return b,e
 }, func(b *base.MemoryMapping) *base.Module {
 at:=freshZeroBegin()'''
 s=replace_once(s,old,new).replace('generated.NewWithMemory(', 'generated.NewWithFreshZeroMemory(')
 s=replace_once(s,'\t\tinstallGuestThreadLifetime(m)','\t\tinstallGuestThreadLifetime(m)\n\t\tfreshZeroEnd("construct",at,m.Memory[:int(m.MemSize.Load())],m.MemSize)')
 s=s.replace('"fmt"','"fmt"\n"sync/atomic"\n"syscall"\n"time"')
 s+='''
// Diagnostic hook: installed once before startup, never changed while guests run.
var FreshZeroHook func(string,[]byte,*atomic.Uint64,float64,float64)
type freshZeroStart struct {at time.Time;cpu float64}
func freshZeroCPU() float64 {var r syscall.Rusage;if e:=syscall.Getrusage(syscall.RUSAGE_SELF,&r);e!=nil {panic(e)};return float64(r.Utime.Sec+r.Stime.Sec)*1000+float64(r.Utime.Usec+r.Stime.Usec)/1000}
func freshZeroBegin() freshZeroStart {if FreshZeroHook==nil {return freshZeroStart{}};return freshZeroStart{time.Now(),freshZeroCPU()}}
func freshZeroEnd(stage string,s freshZeroStart,b []byte,size *atomic.Uint64) {if FreshZeroHook!=nil {wall:=float64(time.Since(s.at).Nanoseconds())/1e6;cpu:=freshZeroCPU()-s.cpu;FreshZeroHook(stage,b,size,wall,cpu)}}
'''
 put(host,s,'memory_backing_unix.go')
 p7='internal/generatedgo/code/p7/p7_pure.go';original=(c/p7).read_text()
 needle='\t\tbase.MemoryFill(m, int32(15244864), v7, int32(8982576))'
 # Consume the capability even in the baseline and regardless of guard branch.
 reset='\tbase.DataDrop(m, 0)'
 original=replace_once(original,reset,'\tm.FreshZeroInit = false\n'+reset)
 overlays={};hashes={}
 for mode in ['baseline','fresh']:
  s=original
  if mode=='fresh':s=replace_once(s,needle,'\t\tif !m.FreshZeroInit {\n'+needle+'\n\t\t}')
  dst=t/(mode+'-p7.go');dst.write_text(s)
  r=dict(replacements);r[str(c/p7)]=str(dst)
  overlay=t/(mode+'-overlay.json');overlay.write_text(json.dumps({'Replace':r})+'\n');overlays[mode]=overlay
  hashes[mode]={str(src.relative_to(c)):dict(original=hashlib.sha256(src.read_bytes()).hexdigest(),overlay=hashlib.sha256(__import__('pathlib').Path(path).read_bytes()).hexdigest()) for key,path in r.items() for src in [__import__('pathlib').Path(key)]}
 return overlays,hashes
