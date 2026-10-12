package base

import (
 "bytes"
 "encoding/binary"
 "os"
 "sync"
 "sync/atomic"
 "testing"
 "unsafe"
)
func allocationModule() *Module {
 b:=make([]byte,65536);size:=new(atomic.Uint64);size.Store(65536)
 return &Module{Memory:b,M:unsafe.Pointer(&b[0]),MemSize:size,MemShared:true}
}
func TestAllocationContracts(t *testing.T) {
 for _,kind:=range []string{"memory","native"} {for _,c:=range []struct{name string;off,n int64;size int64;reject bool}{
  {"inside",0,4,16,false},{"zero",0,0,16,false},{"zero-beyond",32,0,32,false},
  {"grow",16,16,32,false},{"unsigned-wrap",-1,1,16,true},{"signed-limit",1<<63-1,1,16,true},
 } {t.Run(kind+"/"+c.name,func(t *testing.T){
  var f File;var err error
  if kind=="memory" {f,err=NewMemFS().OpenFile("f",os.O_CREATE|os.O_RDWR,0600)} else {f,err=os.CreateTemp(t.TempDir(),"f")}
  if err!=nil {t.Fatal(err)};defer f.Close();f.Write([]byte("0123456789abcdef"));f.Seek(3,0)
  w:=DefaultWASI();w.fdTable[4]=&wasiOpen{f:f};rc:=w.Fd_allocate(nil,4,c.off,c.n)
  if (rc!=0)!=c.reject {t.Fatal("errno",rc)}
  st,_:=f.Stat();if st.Size()!=c.size {t.Fatal("size",st.Size())}
  b:=make([]byte,c.size);f.ReadAt(b,0);if string(b[:16])!="0123456789abcdef"||!bytes.Equal(b[16:],make([]byte,len(b)-16)){t.Fatal("contents changed")}
  pos,_:=f.Seek(0,1);if pos!=3 {t.Fatal("position",pos)}
 })}}
}
func TestAllocationReadonlyAndInvalid(t *testing.T) {
 mem:=NewMemFS();mem.WriteFile("f",[]byte("contents"),0600)
 path:=t.TempDir()+"/f";os.WriteFile(path,[]byte("contents"),0600)
 for _,kind:=range []string{"memory","native"} {t.Run(kind,func(t *testing.T){
  var f File;var err error;if kind=="memory" {f,err=mem.OpenFile("f",os.O_RDONLY,0)}else{f,err=os.Open(path)}
  if err!=nil {t.Fatal(err)};defer f.Close();w:=DefaultWASI();w.fdTable[4]=&wasiOpen{f:f}
  for _,n:=range []int64{0,2,32} {if rc:=w.Fd_allocate(nil,4,0,n);rc!=8 {t.Fatal("readonly",rc)}}
  if rc:=w.Fd_allocate(nil,999,0,0);rc!=8 {t.Fatal("invalid",rc)}
  st,_:=f.Stat();if st.Size()!=8 {t.Fatal("readonly size changed")}
 })}
}
func TestAllocationConcurrentHandles(t *testing.T) {
 for _,kind:=range []string{"memory","native"} {t.Run(kind,func(t *testing.T){
  var files [2]File;var err error
  if kind=="memory" {fs:=NewMemFS();files[0],err=fs.OpenFile("f",os.O_CREATE|os.O_RDWR,0600);files[1],_=fs.OpenFile("f",os.O_RDWR,0)}else{
   p:=t.TempDir()+"/f";files[0],err=os.OpenFile(p,os.O_CREATE|os.O_RDWR,0600);files[1],_=os.OpenFile(p,os.O_RDWR,0)
  }
  if err!=nil {t.Fatal(err)};for _,f:=range files {defer f.Close()};files[0].Write([]byte("0123456789abcdef"))
  ws:=[2]*WasiStubs{DefaultWASI(),DefaultWASI()};for i:=range ws {ws[i].fdTable[4]=&wasiOpen{f:files[i]}}
  // All growth operations must leave the maximum requested size. Any allocator
  // shrink after a concurrent native WASI truncate/write is a failed contract.
  var wg sync.WaitGroup;wg.Add(2)
  go func(){defer wg.Done();m:=allocationModule();copy(m.Memory[32:],[]byte("marker"));binary.LittleEndian.PutUint32(m.Memory[0:],32);binary.LittleEndian.PutUint32(m.Memory[4:],6)
   for i:=0;i<1000;i++ {if ws[0].Fd_filestat_set_size(m,4,4096)!=0 {t.Error("resize")};if ws[0].Fd_pwrite(m,4,0,1,4090,16)!=0 {t.Error("write")}}
  }()
  go func(){defer wg.Done();for i:=0;i<1000;i++ {if ws[1].Fd_allocate(nil,4,0,32)!=0 {t.Error("allocate")}}}()
  wg.Wait();st,_:=files[0].Stat();if st.Size()!=4096 {t.Fatal("allocation shrank concurrent growth",st.Size())}
  b:=make([]byte,6);files[0].ReadAt(b,4090);if string(b)!="marker" {t.Fatal("tail lost",string(b))}
 })}
}
