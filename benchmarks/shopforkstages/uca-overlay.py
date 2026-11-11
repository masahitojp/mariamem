"""Read-only per-collation UCA attribution over the exact canonical guest map."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
S,O=[Path(x).resolve() for x in sys.argv[1:]]
H=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(H/'overlay-detail.py'),str(S),str(O)],check=True)
maps=json.loads((O/'overlay.json').read_text())['Replace'];proof=[]
names=dict(line.split(':',1) for line in (S.parent/'temp/function-map.txt').read_text().splitlines())
def edit(path,fn):
 srcpath=S/path;src=Path(maps.get(str(srcpath),srcpath)).read_text();out=fn(src)
 dst=O/('uca-'+srcpath.name);dst.write_text(out)
 subprocess.run(['/opt/homebrew/bin/gofmt','-w',str(dst)],check=True)
 proof.append(dict(path=path,before=hashlib.sha256(src.encode()).hexdigest(),after=hashlib.sha256(dst.read_bytes()).hexdigest()))
 maps[str(srcpath)]=str(dst)
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
edit('internal/generatedgo/code/base/base.go',lambda s:replace(s,'type Module struct {','type Module struct {\nUCAKey string\nUCAEnter func(int32) func()'))
def runtime(s):
 if '"strconv"' not in s:s=s.replace('import (','import (\n"strconv"',1)
 return replace(s,'details := make(map[string][2]int64)','''details := make(map[string][2]int64)
 // WASM32 CHARSET_INFO: number offset 0; LEX_CSTRING coll_name offsets 24/28.
 // Pinned include/m_ctype.h and observed name/id pairs bind this read-only view.
 m.UCAEnter=func(ptr int32) func() {
  p:=uint32(ptr);read:=func(off uint32) uint32{return binary.LittleEndian.Uint32(m.Memory[p+off:p+off+4])}
  n,q,z:=read(0),read(24),read(28);if z>128 {panic("invalid collation name length")}
  previous:=m.UCAKey;m.UCAKey=strconv.FormatUint(uint64(n),10)+":"+string(m.Memory[q:q+z])
  done:=m.CommonSpan("uca_id:"+m.UCAKey)
  return func(){done();m.UCAKey=previous}
 }''')
edit('internal/generatedgo/runtime_instance.go',runtime)
wrappers={465:('my_coll_init_uca','if m.UCAEnter!=nil {defer m.UCAEnter(l0)()}'),468:('my_uca_info_init','if m.CommonSpan!=nil && m.UCAKey!="" {defer m.CommonSpan("uca_weights:"+m.UCAKey)()}'),610:('my_uca_level_booster_populate','if m.CommonSpan!=nil && m.UCAKey!="" {defer m.CommonSpan("uca_booster:"+m.UCAKey)()}')}
found=set()
for p in (S/'internal/generatedgo/code').glob('p*/p*_pure.go'):
 selected=[n for n in wrappers if re.search(r'^func Fn'+str(n)+r'\(',p.read_text(),re.M)]
 if not selected:continue
 def inject(s):
  for n in selected:
   symbol,code=wrappers[n];assert names[str(n)]==symbol
   match=re.search(r'^func Fn'+str(n)+r'\([^\n]+\{\n',s,re.M);assert match
   end=s.index('\nfunc ',match.end())
   proof.append(dict(function=n,symbol=symbol,body_before_sha256=hashlib.sha256(s[match.start():end].encode()).hexdigest()))
   s=s[:match.end()]+code+'\n'+s[match.end():];found.add(n)
  return s
 edit(str(p.relative_to(S)),inject)
assert found==set(wrappers)
(O/'uca-bindings.json').write_text(json.dumps(proof,indent=2)+'\n')
(O/'overlay.json').write_text(json.dumps({'Replace':maps},indent=2)+'\n')
