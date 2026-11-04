package main
import (
 "bytes"
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "fmt"
 "os"
 "runtime"
 "sync/atomic"
 "syscall"
 "time"
 base "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)
type Segment struct { Begin, End, Destination int }
type Input struct { Path, SHA256 string; Segments []Segment }
func cpu() (int64,int64) { var r syscall.Rusage; if e:=syscall.Getrusage(syscall.RUSAGE_SELF,&r); e!=nil {panic(e)}; return (r.Utime.Sec+r.Stime.Sec)*1e9+(int64(r.Utime.Usec)+int64(r.Stime.Usec))*1000,r.Minflt }
func trial(label,mode string, in Input, data []byte, warmup bool) map[string]any {
 mem,e:=syscall.Mmap(-1,0,32<<20,syscall.PROT_READ|syscall.PROT_WRITE,syscall.MAP_PRIVATE|syscall.MAP_ANON);if e!=nil {panic(e)};defer syscall.Munmap(mem)
 if mode=="pretouched" { for i:=0;i<len(mem);i+=4096 {mem[i]=0} }
 m:=&base.Module{Memory:mem,MemSize:new(atomic.Uint64)};m.MemSize.Store(uint64(len(mem)))
 for _,s:=range in.Segments {m.DataSegs=append(m.DataSegs,data[s.Begin:s.End])}
 c0,f0:=cpu();t:=time.Now()
 for i,s:=range in.Segments {base.MemoryInit(m,i,int32(s.Destination),0,int32(s.End-s.Begin))}
 elapsed:=time.Since(t).Nanoseconds();c1,f1:=cpu()
 for _,s:=range in.Segments {if !bytes.Equal(mem[s.Destination:s.Destination+s.End-s.Begin],data[s.Begin:s.End]) {panic("copy oracle")}}
 return map[string]any{"label":label,"mode":mode,"warmup":warmup,"wall_ns":elapsed,"cpu_ns":c1-c0,"minor_fault_delta":f1-f0,"oracle":true,"copied_bytes":len(data)}
}
func main() {
 raw,e:=os.ReadFile(os.Args[1]);if e!=nil {panic(e)};var inputs map[string]Input;if e=json.Unmarshal(raw,&inputs);e!=nil {panic(e)};payloads:=map[string][]byte{}
 for label,in:=range inputs {data,e:=os.ReadFile(in.Path);if e!=nil {panic(e)};h:=sha256.Sum256(data);if hex.EncodeToString(h[:])!=in.SHA256 {panic("input hash")};payloads[label]=data}
 rows:=[]map[string]any{}
 for _,mode:=range []string{"fresh","pretouched"} {
  for _,label:=range []string{"baseline","candidate"} {rows=append(rows,trial(label,mode,inputs[label],payloads[label],true))}
  for i:=0;i<5;i++ {order:=[]string{"baseline","candidate"};if i%2==1 {order=[]string{"candidate","baseline"}};for _,label:=range order {rows=append(rows,trial(label,mode,inputs[label],payloads[label],false))}}
 }
 result:=map[string]any{"result":"PASS","go":runtime.Version(),"scope":"standalone actual base.MemoryInit component on 32MiB anonymous mmap; excludes guest execution/BSS fill/Fork and mmap/prefault/verification/unmap time","rows":rows}
 out,_:=json.MarshalIndent(result,"","  ");fmt.Println(string(out))
}
