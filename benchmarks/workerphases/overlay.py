"""Read-only counters; no change to worker/scheduler decisions."""
def once(s,a,b):
 assert s.count(a)==1,(a[:70],s.count(a))
 return s.replace(a,b)
def make(c,t):
 src=c/'internal/generatedgo/code/base/base.go';s=src.read_text()
 s=once(s,'\tm.Threads.wg.Add(1)','\tm.Threads.wg.Add(1)\n\tif WorkerObservation!=nil {WorkerObservation("spawn",1)}')
 s=once(s,'\t\tdefer m.Threads.wg.Done()','\t\tdefer m.Threads.wg.Done()\n\t\tdefer func(){if WorkerObservation!=nil {WorkerObservation("exit",1)}}()')
 s=once(s,'\tagents := atomic.AddInt32(&spinAgents, delta)','\tagents := atomic.AddInt32(&spinAgents, delta)\n\tif WorkerObservation!=nil {WorkerObservation("agents",int64(agents))}')
 s=once(s,'func SpinRelax() {','func SpinRelax() {\n\tif WorkerObservation!=nil {WorkerObservation("spin",1)}')
 s=once(s,'if atomic.LoadUint32(&spinOversubscribed) != 0 || n&1023 == 0 {','if atomic.LoadUint32(&spinOversubscribed) != 0 || n&1023 == 0 {\n\t\tif WorkerObservation!=nil {WorkerObservation("yield",1);if atomic.LoadUint32(&spinOversubscribed)!=0 {WorkerObservation("yield_oversubscribed",1)}}')
 signature='func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {'
 s=once(s,signature,signature.replace(') int32 {',') (result int32) {')+'''
 var started time.Time
 if WorkerObservation!=nil {WorkerObservation("wait_start",1);started=time.Now();defer func(){d:=time.Since(started);WorkerObservation("wait_return_"+strconv.Itoa(int(result)),1);WorkerObservation("wait_ns",int64(d));if result==0&&d<time.Millisecond {WorkerObservation("wait_woken_short",1)}}()}
''')
 s=once(s,'\tfor _, ch := range waiters[:n] {','\tif WorkerObservation!=nil {WorkerObservation("notify",1);WorkerObservation("woken",int64(n))}\n\tfor _, ch := range waiters[:n] {')
 s+='\n// Observation installed once before any guest starts, never changed while running.\nvar WorkerObservation func(string,int64)\n'
 dst=t/'base.go';dst.write_text(s);return src,dst
