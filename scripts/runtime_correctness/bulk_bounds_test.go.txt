package base
import("bytes";"sync/atomic";"testing";"unsafe")
func TestBulkBoundsAndEffects(t *testing.T){
 for _,op:=range []string{"fill","copy","init"}{for _,c:=range []struct{name string;dst,src,n int32;drop,trap bool}{
  {"end",65536,0,0,false,false},{"past-dst",65537,0,0,false,true},{"unsigned-dst",-1,0,0,false,true},
  {"end-src",0,65536,0,false,false},{"past-src",0,65537,0,false,true},{"unsigned-length",0,0,-1,false,true},
  {"one-valid",2,0,1,false,false},{"one-invalid",65536,0,1,false,true},
  {"dropped-empty",65536,0,0,true,false},{"dropped-past",0,1,0,true,true},{"dropped-copy",0,0,1,true,true},
 }{if op=="fill"&&(c.drop||c.name=="end-src"||c.name=="past-src"){continue};if op=="copy"&&c.drop{continue}
 t.Run(op+"/"+c.name,func(t *testing.T){b:=make([]byte,131072);b[0]=9;size:=new(atomic.Uint64);size.Store(65536);m:=&Module{Memory:b,M:unsafe.Pointer(&b[0]),MemSize:size,DataSegs:[][]byte{make([]byte,65536)}}
  m.DataSegs[0][0]=5
  if c.drop{DataDrop(m,0)};before:=append([]byte(nil),b...);trapped:=false
  func(){defer func(){trapped=recover()!=nil}();switch op{case "fill":MemoryFill(m,c.dst,7,c.n);case "copy":MemoryCopy(m,c.dst,c.src,c.n);case "init":MemoryInit(m,0,c.dst,c.src,c.n)}}()
  if trapped!=c.trap{t.Fatalf("trap=%v want=%v",trapped,c.trap)}
  if c.name=="one-valid" {want:=byte(7);if op=="copy"{want=9};if op=="init"{want=5};if b[2]!=want{t.Fatal("valid effect",b[2],want)}}
  if (c.n==0||c.trap)&&!bytes.Equal(b,before){t.Fatal("changed memory on empty/trap")}
 })}}
}
