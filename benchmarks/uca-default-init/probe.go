package generatedgo

import (
 "encoding/binary"
 "encoding/json"
 "os"
 "sync"
 "sync/atomic"
 "time"
 "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)
var ucaProbeSequence atomic.Uint64
var ucaProbeOutput sync.Mutex
func attachUCAProbe(m *base.Module, restored bool) {
 path:=os.Getenv("UCA_SUBPHASE_PATH");if path=="" {return}
 instance:=ucaProbeSequence.Add(1)
 var phases map[string][2]int64
 var phase string
 var start,timePhase time.Time
 m.UCAPhase=func(next string) {
  if phases==nil {return};now:=time.Now()
  if phase!="" {v:=phases[phase];v[1]+=now.Sub(timePhase).Nanoseconds();phases[phase]=v}
  phase=next;timePhase=now
  if next!="" {v:=phases[next];v[0]++;phases[next]=v}
 }
 m.UCAStart=func(ptr int32) func() {
  p:=uint32(ptr);id:=binary.LittleEndian.Uint32(m.Memory[p:p+4])
  if id!=2048&&id!=2304&&id!=2560&&id!=2816&&id!=3072 {return func(){}}
  if phases!=nil {panic("nested UCA probe")}
  q:=binary.LittleEndian.Uint32(m.Memory[p+24:p+28]);n:=binary.LittleEndian.Uint32(m.Memory[p+28:p+32]);if n>128 {panic("UCA name length")}
  name:=string(m.Memory[q:q+n]);phases=map[string][2]int64{};phase="";start=time.Now()
  return func(){
   elapsed:=time.Since(start).Nanoseconds();m.UCAPhase("")
   data,e:=json.Marshal(map[string]any{"instance":instance,"restored":restored,"id":id,"name":name,"total_ns":elapsed,"phases":phases});if e!=nil {panic(e)}
   phases=nil;phase=""
   ucaProbeOutput.Lock();defer ucaProbeOutput.Unlock()
   f,e:=os.OpenFile(path,os.O_CREATE|os.O_APPEND|os.O_WRONLY,0600);if e!=nil {panic(e)}
   _,e=f.Write(append(data,'\n'));if e!=nil {f.Close();panic(e)};if e=f.Close();e!=nil {panic(e)}
  }
 }
}
