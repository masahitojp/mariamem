from pathlib import Path
import json
r=Path(__file__).resolve().parents[1];src=r/'worktree/internal/guest/linked.go';s=src.read_text();s=s.replace('"context"','"context"\n "encoding/binary"\n "encoding/json"\n "path/filepath"\n "sync"\n "sync/atomic"')
s=s.replace('execution := generatedgo.StartInstance(childIn, childOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)', '''var guestIn io.Reader=childIn
 var guestOut io.Writer=childOut
 var hostIn io.WriteCloser=in
 var hostOut io.ReadCloser=out
 var ledger *ipcLedger
 if os.Getenv("IPC_DIAG_DIR")!="" {
  label,_:=ctx.Value("mariamem_benchmark_label").(string)
  ledger=&ipcLedger{ID:ipcIDs.Add(1), Label:label, Directions:map[string]*ipcCounter{}}
  guestIn=&ipcReader{Reader:childIn,c:ledger.counter("guest_read",true)}
  guestOut=&ipcWriter{Writer:childOut,c:ledger.counter("guest_write",false)}
  hostIn=&ipcWriteCloser{WriteCloser:in,c:ledger.counter("host_write",true)}
  hostOut=&ipcReadCloser{ReadCloser:out,c:ledger.counter("host_read",false)}
 }
 execution := generatedgo.StartInstance(guestIn, guestOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)
 if ledger!=nil {
  observedDone:=make(chan error,1)
  go func(){e:=<-execution;ledger.save();observedDone<-e}()
  execution=observedDone
 }''')
# Capture channel in closure before variable replacement; otherwise closure may self-wait.
s=s.replace('go func(){e:=<-execution;ledger.save();observedDone<-e}()', 'originalDone:=execution\n  go func(){e:=<-originalDone;if e!=nil{ledger.ExitError=e.Error()};ledger.save();observedDone<-e}()')
s=s.replace('ConnectWithFailure(ctx, in, out, execution,', 'ConnectWithFailure(ctx, hostIn, hostOut, execution,')
s+='''
// Disposable observation only. Calls preserve the original os.Pipe endpoints.
var ipcIDs atomic.Uint64
type ipcCounter struct {
 mu sync.Mutex
 Calls uint64 `json:"calls"`
 Bytes uint64 `json:"bytes"`
 Nanoseconds uint64 `json:"call_elapsed_ns"`
 Errors uint64 `json:"errors"`
 Sizes map[int]uint64 `json:"returned_sizes"`
 Frames uint64 `json:"frames"`
 ZeroFrames uint64 `json:"zero_frames"`
 ExportFrames uint64 `json:"export_frames"`
 FrameBytes uint64 `json:"frame_payload_bytes"`
 FrameSizes map[uint32]uint64 `json:"frame_sizes"`
 Opcodes map[byte]uint64 `json:"opcodes,omitempty"`
 header [4]byte
 hn int
 remaining uint32
 first bool
 request bool
}
func(c *ipcCounter)record(b []byte,t time.Time,e error){
 elapsed:=time.Since(t)
 c.mu.Lock();defer c.mu.Unlock()
 c.Calls++;c.Bytes+=uint64(len(b));c.Nanoseconds+=uint64(elapsed);if e!=nil{c.Errors++};c.Sizes[len(b)]++
 for len(b)>0 {
  if c.remaining==0 {
   n:=copy(c.header[c.hn:],b);c.hn+=n;b=b[n:]
   if c.hn<4 {break};c.hn=0;c.remaining=binary.LittleEndian.Uint32(c.header[:]);c.first=true
   if c.remaining==0 {c.ZeroFrames++;continue}
   if c.request && c.remaining==0xfffffffe {c.ExportFrames++;c.remaining=0;continue}
   c.Frames++;c.FrameBytes+=uint64(c.remaining);c.FrameSizes[c.remaining]++
  }
  if len(b)==0 {break}
  if c.first&&c.request {c.Opcodes[b[0]]++};c.first=false
  n:=len(b);if uint32(n)>c.remaining{n=int(c.remaining)};b=b[n:];c.remaining-=uint32(n)
 }
}
type ipcLedger struct {Label string `json:"label"`; ExitError string `json:"exit_error"`; ID uint64 `json:"db_instance"`;Directions map[string]*ipcCounter `json:"directions"`}
func(l *ipcLedger)counter(name string,request bool)*ipcCounter{c:=&ipcCounter{Sizes:map[int]uint64{},FrameSizes:map[uint32]uint64{},Opcodes:map[byte]uint64{},request:request};l.Directions[name]=c;return c}
func(l *ipcLedger)save(){
 // Guest workers have joined. Host EOF/close may still be finishing.
 for _,k:=range []string{"guest_read","guest_write","host_read","host_write"}{l.Directions[k].mu.Lock()}
 b,e:=json.Marshal(l)
 for _,k:=range []string{"host_write","host_read","guest_write","guest_read"}{l.Directions[k].mu.Unlock()}
 if e!=nil{panic(e)}
 p:=filepath.Join(os.Getenv("IPC_DIAG_DIR"),fmt.Sprintf("db-%03d.json",l.ID))
 if e=os.WriteFile(p,b,0644);e!=nil{panic(e)}
}
type ipcReader struct{io.Reader;c *ipcCounter}
func(r *ipcReader)Read(b []byte)(int,error){t:=time.Now();n,e:=r.Reader.Read(b);r.c.record(b[:n],t,e);return n,e}
type ipcWriter struct{io.Writer;c *ipcCounter}
func(w *ipcWriter)Write(b []byte)(int,error){t:=time.Now();n,e:=w.Writer.Write(b);w.c.record(b[:n],t,e);return n,e}
type ipcReadCloser struct{io.ReadCloser;c *ipcCounter}
func(r *ipcReadCloser)Read(b []byte)(int,error){t:=time.Now();n,e:=r.ReadCloser.Read(b);r.c.record(b[:n],t,e);return n,e}
type ipcWriteCloser struct{io.WriteCloser;c *ipcCounter}
func(w *ipcWriteCloser)Write(b []byte)(int,error){t:=time.Now();n,e:=w.WriteCloser.Write(b);w.c.record(b[:n],t,e);return n,e}
'''
dst=r/'temp/linked_overlay.go';dst.write_text(s);(r/'evidence/overlay.json').write_text(json.dumps({'Replace':{str(src):str(dst)}},indent=2))
