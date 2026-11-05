from pathlib import Path
w=Path('.');p=w/'temp/tools/runtime_wire.go.txt';s=p.read_text();s=s.replace('var wireLibraryMode sync.Once','''// Lifecycle is private to this experiment. Approval is not a guest join.
type WireLifecycle struct {
 Capture *prepared.Capture
 Approval <-chan error
 Observe func(string)
}
func (l *WireLifecycle) observe(event string){if l.Observe!=nil{l.Observe(event)}}
var wireLibraryMode sync.Once''')
s=s.replace('captures ...*prepared.Capture','life *WireLifecycle').replace('epoch, captures...)','epoch, life)')
s=s.replace('if len(captures) > 0 && captures[0] != nil {','if life==nil || life.Capture==nil || life.Approval==nil {err=fmt.Errorf("capture lifecycle required");return}\n  {',1).replace('captures[0].BindRootSource','life.Capture.BindRootSource')
s=s.replace('if epoch == 0 || restore != nil || transfer != "" || len(captures) != 0 {','if epoch == 0 || transfer != "" {').replace('wire experiment requires fresh nonzero instance identity','wire experiment requires nonzero instance identity and no transfer')
s=s.replace('wireGuestEnvironment(false, guestTiming)','wireGuestEnvironment(restore != nil, guestTiming)')
s=s.replace('defer releaseMemoryModule(m, release, &err)','defer func(){releaseMemoryModule(m,release,&err);life.observe("memory_released")}()')
s=s.replace('if len(captures) > 0 && captures[0] != nil && captures[0].Requested() {\n\t\t\terr = fs.FreezeRoot(GuestSHA256, captures[0])','life.observe("guest_joined")\n  if life.Capture.Requested() {\n   if err= <-life.Approval;err!=nil{return}\n   life.observe("capture_approved")\n   life.observe("freeze_begin")\n\t\t\terr = fs.FreezeRoot(GuestSHA256, life.Capture)\n   if err==nil{life.observe("freeze_complete")}')
p.write_text(s)
p=w/'temp/tools/main.go.txt';s=p.read_text();s=s.replace('"encoding/binary"','"encoding/binary"\n "encoding/json"\n "context"\n "github.com/masahitojp/mariamem/internal/prepared"\n stored "github.com/masahitojp/mariamem/internal/snapshot"\n "github.com/masahitojp/mariamem/internal/forklimit"')
s=s.replace('type instance struct {','''type instance struct {
 capture prepared.Capture
 approval chan error
 approvalOnce sync.Once
 readDone chan struct{}
 checking,consumed bool
 captureID uint64
 stopRequest uint32
 stopAcked,stopReceipt bool
 lifecycleEvents []string
 operation chan struct{}
 dropKinds map[byte]bool
 wrongReceipt bool
 lease *forklimit.Lease
 captureDebt error
 retained []*stored.Owned
 holdJoin <-chan struct{}
''')
s=s.replace('func newInstance(ms uint64) (*instance, error) {','func newInstance(ms uint64) (*instance,error){return newRestored(ms,nil)}\nfunc newRestored(ms uint64, restore []prepared.Entry) (*instance,error){')
s=s.replace('limit: ms}', 'limit: ms,approval:make(chan error,1),readDone:make(chan struct{}),operation:make(chan struct{},1),dropKinds:map[byte]bool{}}')
s=s.replace('os.Stderr, "", nil, false,','os.Stderr, "", restore, false,').replace('r.epoch)\n\tr.wg.Add(1)','r.epoch,&generatedgo.WireLifecycle{Capture:&r.capture,Approval:r.approval,Observe:r.note})\n\tr.wg.Add(1)',1)
s=s.replace('go func() { defer r.wg.Done(); r.readLoop() }()','go func() { defer r.wg.Done();defer close(r.readDone);r.readLoop() }()')
s=s.replace('return nil, fmt.Errorf("runtime before ready: %v", r.result())','return r, fmt.Errorf("runtime before ready: %v", r.result())')
s=s.replace('func (r *instance) fail(e error) {','func(r *instance) note(e string){r.mu.Lock();r.lifecycleEvents=append(r.lifecycleEvents,e);r.mu.Unlock()}\nfunc(r *instance) resolve(e error){r.approvalOnce.Do(func(){r.approval<-e})}\nfunc (r *instance) fail(e error) {\n r.resolve(e)')
s=s.replace('func (r *instance) rpc(f frame, initial ...*session) (frame, error) {','''func (r *instance) rpc(f frame, initial ...*session) (frame,error){ctx,cancel:=context.WithTimeout(context.Background(),8*time.Second);defer cancel();return r.rpcContext(ctx,f,initial...)}
func (r *instance) rpcContext(ctx context.Context,f frame, initial ...*session) (frame, error) {''')
s=s.replace('r.pending[id] = ch','r.pending[id] = ch\n if f.kind==12 {r.stopRequest=id}',1).replace('case <-time.After(8 * time.Second):\n\t\treturn frame{}, errors.New("control deadline")','case <-ctx.Done():\n\t\treturn frame{}, ctx.Err()')
s=s.replace('r.mu.Lock()\n\t\tif len(r.events)', '''r.mu.Lock()
  drop:=r.dropKinds[f.kind]
  wrong:=r.wrongReceipt
  r.mu.Unlock()
  if drop{continue}
  if wrong&&f.kind==114{f.value++}
  if f.kind==114{
   r.mu.Lock();valid:=r.consumed&&r.captureID!=0&&f.value==r.captureID&&f.request==r.stopRequest;acked:=r.stopAcked;if valid{r.stopReceipt=true;r.lifecycleEvents=append(r.lifecycleEvents,"capture_stopped")};r.mu.Unlock()
   if !valid{r.fail(errors.New("wrong capture receipt"));continue};if acked{r.resolve(nil)};continue
  }
  r.mu.Lock()
\t\tif len(r.events)''',1)
s=s.replace('case ready:\n\t\t\tclose(r.ready)','''case ready:
   var profile struct{Lifecycle int `json:"lifecycle_profile"`};if json.Unmarshal(f.body,&profile)!=nil||profile.Lifecycle!=1{r.fail(errors.New("wrong lifecycle profile"));return}
\t\t\tclose(r.ready)''')
s=s.replace('r.mu.Lock();r.finalStats=append([]byte(nil),f.body...);r.mu.Unlock()','r.mu.Lock();r.finalStats=append([]byte(nil),f.body...);receipt:=r.stopReceipt;r.mu.Unlock();if r.capture.Requested()&&!receipt{r.fail(errors.New("missing capture receipt"))}')
# Reader EOF must unblock disposition even if the root has already returned.
s=s.replace('if e != nil {\n\t\t\tselect {\n\t\t\tcase <-r.done:', 'if e != nil {\n   r.resolve(fmt.Errorf("capture transport ended: %w",e))\n\t\t\tselect {\n\t\t\tcase <-r.done:',1)
# admission check and WaitGroup Add are under the same mutex as stop/checking.
s=s.replace('r.wg.Add(1)\n\t\t\tgo func() { defer r.wg.Done(); r.attach(c) }()', 'r.mu.Lock();deny:=r.stopping||r.checking||r.consumed;if !deny{r.wg.Add(1)};r.mu.Unlock();if deny{c.Close();continue}\n\t\t\tgo func() { defer r.wg.Done(); r.attach(c) }()')
s=s.replace('func (r *instance) close() error {','func (r *instance) close() error {\n r.resolve(errors.New("ordinary close cannot approve capture"))')
s=s.replace('\t\tr.wg.Wait()\n\t\tr.out.Close()','\t\tr.wg.Wait()\n  if r.holdJoin!=nil{<-r.holdJoin}\n  if r.lease!=nil{r.lease.Settle(r.captureDebt)}\n\t\tr.out.Close()',1)
# Replace close with common ordered teardown helpers; snapshot must not call it.
a=s.index('func main()');s=s[:a]+'''func(r *instance) stopIngress(){
 r.mu.Lock();r.stopping=true;l:=r.listener;all:=make([]*session,0,len(r.sessions));for _,s:=range r.sessions{all=append(all,s)};r.mu.Unlock()
 if l!=nil{l.Close()};for _,s:=range all{s.close()}
}
func(r *instance) awaitJoined(ctx context.Context)error{
 select{case <-r.done:case <-ctx.Done():if r.lease!=nil{r.lease.Settle(ctx.Err())};return fmt.Errorf("join incomplete; resources retained: %w",ctx.Err())}
 select{case <-r.readDone:case <-ctx.Done():return fmt.Errorf("reader join incomplete: %w",ctx.Err())}
 r.wg.Wait();r.in.Close();r.out.Close();if r.lease!=nil{r.lease.Settle(r.captureDebt)};r.note("host_joined");return r.result()
}
func(r *instance) failCapture(ctx context.Context,e error)(*stored.Owned,bool,error){
 r.mu.Lock();r.consumed=true;r.checking=false;r.mu.Unlock();r.capture.Discard();r.fail(e);r.stopIngress();go r.send(frame{kind:stop});joined:=r.awaitJoined(ctx);return nil,true,errors.Join(e,joined)
}
func(r *instance) snapshot(ctx context.Context,rollback bool)(*stored.Owned,bool,error){
 select{case r.operation<-struct{}{}:defer func(){<-r.operation}();case <-ctx.Done():return nil,false,ctx.Err()}
 r.mu.Lock();if r.stopping||r.consumed||r.errorCause!=nil{r.mu.Unlock();return nil,true,errors.New("source consumed or failed")};r.checking=true;r.captureID=uint64(r.sequence.Add(1));id:=r.captureID;r.mu.Unlock()
 if e:=ctx.Err();e!=nil{r.mu.Lock();r.checking=false;r.mu.Unlock();return nil,false,e}
 flag:=uint64(0);if rollback{flag=1};reply,e:=r.rpcContext(ctx,frame{kind:11,value:id,generation:flag})
 if e!=nil{return r.failCapture(ctx,e)}
 if reply.kind==110&&(reply.value==1||reply.value==2){r.mu.Lock();r.checking=false;r.mu.Unlock();return nil,false,fmt.Errorf("capture precondition %d: %s",reply.value,reply.body)}
 if reply.kind!=112||reply.value!=id{return r.failCapture(ctx,errors.New("invalid capture fence"))}
 r.mu.Lock();r.consumed=true;r.mu.Unlock();r.note("fenced");r.capture.Request()
 reply,e=r.rpcContext(ctx,frame{kind:12,value:id});if e!=nil{return r.failCapture(ctx,e)}
 if reply.kind!=113||reply.value!=id{return r.failCapture(ctx,errors.New("invalid capture stop acceptance"))}
 if e=ctx.Err();e!=nil{return r.failCapture(ctx,e)}
 r.mu.Lock();r.stopAcked=true;receipt:=r.stopReceipt;r.mu.Unlock();r.note("stop_accepted");if receipt{r.resolve(nil)};r.stopIngress()
 if e=r.awaitJoined(ctx);e!=nil{return r.failCapture(ctx,e)}
 image,e:=r.capture.TakeRoot(generatedgo.GuestSHA256);if e!=nil{return nil,true,e};owned,e:=stored.OwnRoot(image,generatedgo.GuestSHA256);if e!=nil{return nil,true,e};r.note("root_owned");return owned,true,nil
}
type baseline struct{backing *stored.Owned;pool *forklimit.Pool}
func makeBaseline(o *stored.Owned)*baseline{p,e:=forklimit.New(2);if e!=nil{panic(e)};return &baseline{o,p}}
func(b *baseline) fork(ctx context.Context)(*instance,error){
 lease,e:=b.pool.Acquire(ctx);if e!=nil{return nil,e};entries,release,e:=b.backing.Acquire(generatedgo.GuestSHA256);if e!=nil{lease.Cancel();return nil,e};defer release();if e=lease.Activate();e!=nil{return nil,e}
 r,e:=newRestored(5000,entries);if r!=nil{r.lease=lease};if e!=nil{if r!=nil{cleanupCtx,cancel:=context.WithTimeout(context.Background(),3*time.Second);joined:=r.awaitJoined(cleanupCtx);cancel();if joined!=nil{lease.Settle(joined)}else{lease.Settle(nil)}}else{lease.Settle(e)};return r,e};return r,nil
}
func(b *baseline) close()error{b.pool.Close();return b.backing.Close()}
func main(){}
'''
p.write_text(s)
