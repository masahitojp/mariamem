//go:build (darwin && arm64) || (linux && amd64)

package base

import (
 "encoding/binary"
 "sync"
 "sync/atomic"
 "syscall"
 "testing"
 "unsafe"
)
func narrowTestModule(t *testing.T,mapped bool)*Module{
 t.Helper();var b []byte
 if mapped {owner,err:=NewMemoryMapping(65536,131072);if err!=nil{t.Fatal(err)};b=owner.Bytes();t.Cleanup(func(){if err:=owner.Close();err!=nil{t.Error(err)}})}else{b=make([]byte,131072)}
 size:=new(atomic.Uint64);size.Store(65536);return &Module{Memory:b,M:unsafe.Pointer(&b[0]),MemSize:size,MemShared:true}
}
func narrowMustTrap(t *testing.T,f func()){t.Helper();did:=false;func(){defer func(){did=recover()!=nil}();f()}();if !did{t.Fatal("missing trap")}}
func TestNarrowAtomicValuesBounds(t *testing.T){
 for _,mapped:=range []bool{false,true}{m:=narrowTestModule(t,mapped);copy(m.Memory[64:68],[]byte{0xff,0x80,0xaa,0x91});m.Memory[65535]=0xfe
 for _,contended:=range []bool{false,true}{if contended{ForceContendedAtomics(m)}
  for lane:=int32(0);lane<4;lane++ {if got:=AtomicLoad32_8u(m,64+lane,0);got!=int32(m.Memory[64+lane]){t.Fatal(got)}}
  for _,lane:=range []int32{0,2}{if got:=AtomicLoad32_16u(m,64+lane,0);got!=int32(binary.LittleEndian.Uint16(m.Memory[64+lane:])){t.Fatal(got)}}
  if AtomicLoad32_8u(m,65535,0)!=254{t.Fatal("last valid byte")}
  for _,f:=range []func(){func(){AtomicLoad32_8u(m,65536,0)},func(){AtomicLoad32_8u(m,-1,0)},func(){AtomicLoad32_8u(m,-1,1)},func(){AtomicLoad32_16u(m,65,0)},func(){AtomicLoad32_16u(m,65536,0)}}{narrowMustTrap(t,f)}
 }}
}
func TestNarrowAtomicReadonlyMapping(t *testing.T){
 m:=narrowTestModule(t,true);m.Memory[66]=0xff;m.Memory[67]=0x81;ForceContendedAtomics(m)
 if err:=syscall.Mprotect(m.Memory[:65536],syscall.PROT_READ);err!=nil{t.Fatal(err)}
 if AtomicLoad32_8u(m,66,0)!=255||AtomicLoad32_16u(m,66,0)!=0x81ff{t.Fatal("readonly value")}
}
func TestNarrowAtomicPublication(t *testing.T){
 for _,mapped:=range []bool{false,true}{m:=narrowTestModule(t,mapped);ForceContendedAtomics(m)
 flag:=(*uint32)(unsafe.Add(m.M,64));payload:=(*uint32)(unsafe.Add(m.M,128))
 for _,bits:=range []int{8,16}{for repeat:=0;repeat<1000;repeat++{
  atomic.StoreUint32(flag,0);atomic.StoreUint32(payload,0);var wg sync.WaitGroup;wg.Add(1)
  go func(){defer wg.Done();atomic.StoreUint32(payload,0x12345678);atomic.StoreUint32(flag,1)}()
  for {var v int32;if bits==8{v=AtomicLoad32_8u(m,64,0)}else{v=AtomicLoad32_16u(m,64,0)};if v!=0{break}}
  if atomic.LoadUint32(payload)!=0x12345678{t.Fatal("publication ordering")};wg.Wait()
 }}
 }
}
