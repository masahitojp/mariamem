"""Extend the existing exact-bound observer with nested aggregate timers."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
S,O=[Path(x).resolve() for x in sys.argv[1:]]
H=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(H/'overlay.py'),str(S),str(O)],check=True)
maps=json.loads((O/'overlay.json').read_text())['Replace']
proof=[]
names=dict(line.split(':',1) for line in (S.parent/'temp/function-map.txt').read_text().splitlines())
for n,name in [(465,'my_coll_init_uca'),(794,'alloc_dynamic'),(814,'my_hash_insert'),(961,'init_available_charsets'),(967,'get_internal_charset')]:assert names[str(n)]==name

def edit(path,fn):
 original=S/path;src=Path(maps.get(str(original),original)).read_text();dst=O/('detail-'+original.name)
 out=fn(src);dst.write_text(out)
 subprocess.run(['/opt/homebrew/bin/gofmt','-w',str(dst)],check=True)
 proof.append(dict(path=path,input_sha256=hashlib.sha256(src.encode()).hexdigest(),output_sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
 maps[str(original)]=str(dst)

def replace(src,a,b):
 assert src.count(a)==1,(a,src.count(a));return src.replace(a,b)
edit('internal/generatedgo/code/base/base.go',lambda s:replace(s,'type Module struct {','type Module struct {\nCommonSpan func(string) func()\nCommonRegistry bool\nCommonCounts [4]uint64'))
edit('internal/timing/timing.go',lambda s:replace(replace(s,'type Trace struct {','type Trace struct {\nCommonDetails map[string][2]int64 `json:"common_details,omitempty"`\nCommonCounts []uint64 `json:"common_counts,omitempty"`'), 'var sequence atomic.Uint64','''func SetCommonDetails(ctx context.Context, details map[string][2]int64, counts []uint64) {
 if t,ok:=ctx.Value(key{}).(*Trace);ok {t.mu.Lock();t.CommonDetails=details;t.CommonCounts=counts;t.mu.Unlock()}
}
var sequence atomic.Uint64'''))
rt='internal/generatedgo/runtime_instance.go'
def runtime(s):
 if '"time"' not in s:s=s.replace('import (','import (\n"time"',1)
 s=replace(s,'m.CommonMark = func(name string) {','''details:=make(map[string][2]int64)
 m.CommonSpan=func(name string) func() {start:=time.Now();return func(){d:=details[name];d[0]++;d[1]+=time.Since(start).Nanoseconds();details[name]=d}}
 m.CommonMark = func(name string) {''')
 s=replace(s,'m.CommonMark = nil','''counts:=append([]uint64(nil),m.CommonCounts[:]...)
 var registered uint64
 for i:=0;i<4096;i++ {if binary.LittleEndian.Uint32(m.Memory[18161040+i*4:18161044+i*4])!=0 {registered++}}
 counts=append(counts,registered)
 timing.SetCommonDetails(ctx,details,counts)
 m.CommonSpan=nil
 m.CommonMark = nil''')
 return s
edit(rt,runtime)
# Millisecond resolution probe entry and its single result-store continuation.
def timer(s):
 start=s.index('func Fn5573(');end=s.index('\nfunc ',start+1);b=s[start:end]
 for event,a in [('timer_ms_begin','L1362:\n\t;\n\tv5763 = int32(10000000)'),('timer_ms_end','L1361:\n\t;\n\t*(*int64)(unsafe.Add(mBase, base.MemoryEA(m, 26639800, 0, 8))) = v5911')]:
  assert b.count(a)==1
  b=b.replace(a,a[:len('L1362:\n\t;\n')]+'\tif m.CommonMark!=nil {m.CommonMark("'+event+'")}\n'+a[len('L1362:\n\t;\n'):])
 return s[:start]+b+s[end:]
edit('internal/generatedgo/code/p0/p0_pure.go',timer)
# Function entry/exit instrumentation, with source body hashes and exact symbol binding.
wrappers={
 465:'if cb:=m.CommonSpan;cb!=nil {defer cb("uca_deep")()}\n',
 967:'if cb:=m.CommonSpan;cb!=nil {defer cb("selected_charset")()}\n',
 961:'if m.CommonSpan!=nil {m.CommonRegistry=true;defer func(){m.CommonRegistry=false}()}\n',
 814:'if m.CommonRegistry {if l0==18177424 {m.CommonCounts[0]++};if l0==18177488 {m.CommonCounts[1]++}}\n',
 794:'''if m.CommonRegistry && (l0==18177444 || l0==18177508) && *(*uint32)(unsafe.Add(m.M,uintptr(uint32(l0))+4))==*(*uint32)(unsafe.Add(m.M,uintptr(uint32(l0))+8)) {
 key:="charset_hash_grow";idx:=2;if l0==18177508 {key="collation_hash_grow";idx=3};m.CommonCounts[idx]++;if cb:=m.CommonSpan;cb!=nil {defer cb(key)()}
 }\n''',
}
found=set()
for p in (S/'internal/generatedgo/code').glob('p*/p*_pure.go'):
 canonical=p.read_text();selected=[n for n in wrappers if re.search(r'^func Fn'+str(n)+r'\(',canonical,re.M)]
 if not selected:continue
 def inject(s):
  for n in selected:
   match=re.search(r'^func Fn'+str(n)+r'\([^\n]+\{\n',s,re.M);assert match
   end=s.index('\nfunc ',match.end());body=s[match.start():end]
   proof.append(dict(function=n,symbol=names[str(n)],body_before_sha256=hashlib.sha256(body.encode()).hexdigest()))
   added='\t'+wrappers[n];s=s[:match.end()]+added+s[match.end():];found.add(n)
  return s
 edit(str(p.relative_to(S)),inject)
assert found==set(wrappers)
(O/'detail-bindings.json').write_text(json.dumps(proof,indent=2)+'\n')
(O/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n')
