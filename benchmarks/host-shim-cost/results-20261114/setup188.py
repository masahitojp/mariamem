from pathlib import Path
import subprocess,tarfile,io,json,shutil
W=Path('build/experiment-work/host-shim-cost').resolve();E=W/'evidence';T=W/'temp';S=W/'worktree'
prefix='benchmarks/insert-trigger-stages/results-20261114/sum-control/'
t=tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive','706072d8',prefix])))
for m in t.getmembers():
 if m.isfile():
  p=E/m.name[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
subprocess.run(['python3',str(E/'restore.py')],check=True);subprocess.run(['python3',str(E/'extend.py')],check=True)
o=json.loads((E/'overlay.json').read_text());R=o['Replace']
def put(rel,s):
 p=T/('obs-'+rel.replace('/','_'));p.write_text(s);R[str(S/rel)]=str(p)
def read(rel):return Path(R.get(str(S/rel),str(S/rel))).read_text()
def edit(rel,a,b,n=1):
 s=read(rel);assert s.count(a)==n,(rel,a,s.count(a));put(rel,s.replace(a,b))
base='internal/generatedgo/code/base/'
edit(base+'base.go','ExperimentCurrent *ExperimentRecord','Obs *ObsInstance\n ExperimentCurrent *ExperimentRecord')
edit(base+'experiment_stages.go','ExperimentMark(m,0)','ExperimentMark(m,0);if m.Obs!=nil {m.Obs.Mark(id, "worker_begin")}')
edit(base+'experiment_stages.go','r.T[i]=ExperimentNow();r.Counts[i]++','r.T[i]=ExperimentNow();r.Counts[i]++;if m.Obs!=nil {m.Obs.At(r.ID,fmt.Sprintf("stage%d",i),r.T[i])}')
edit('internal/generatedgo/runtime_instance.go','defer releaseMemoryModule(m, release, &err)','if v,ok:=in.(interface{Observation()*base.ObsInstance});ok{m.Obs=v.Observation()}\n defer releaseMemoryModule(m, release, &err)')
rel='internal/guest/linked.go';s=read(rel).replace('"context"','"context"\n "github.com/masahitojp/mariamem/internal/generatedgo/code/base"')
a='execution := generatedgo.StartInstance(childIn, childOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)';assert a in s
s=s.replace(a,'''var obs *base.ObsInstance
 var reader io.Reader=childIn
 if base.ObsEnabled { label,_:=ctx.Value("mariamem_benchmark_label").(string);obs=base.NewObs(label);reader=&obsReader{Reader:childIn,obs:obs} }
 execution := generatedgo.StartInstance(reader, childOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)''').replace('return p, e','if p!=nil{p.obs=obs};return p, e');put(rel,s)
rel='internal/guest/guest.go';s=read(rel).replace('"context"','"context"\n "github.com/masahitojp/mariamem/internal/generatedgo/code/base"');s=s.replace('type Process struct {','type Process struct {\n obs *base.ObsInstance')
s=s.replace('func (p *Process) write(ctx context.Context, b []byte) error {','func (p *Process) write(ctx context.Context, b []byte) error {\n id:=int32(binary.LittleEndian.Uint32(b[5:]));p.obs.Mark(id,"queue_begin")')
s=s.replace('complete := make(chan error, 1)','p.obs.Mark(id,"queue_acquired")\n complete := make(chan error, 1)')
s=s.replace('go func() { complete <- writeAll(p.in, b) }()','go func() {p.obs.Mark(id,"write_begin");err:=writeAll(p.in,b);p.obs.Mark(id,"write_end");complete<-err}()')
s=s.replace('ch := make(chan response, 1)','callAt:=base.ObsNow()\n ch := make(chan response, 1)')
s=s.replace('p.pending[id] = ch','p.pending[id] = ch\n p.obs.At(int32(id),"call_begin",callAt)')
s=s.replace('case r := <-ch:\n\t\treturn r.result, r.err','case r := <-ch:\n p.obs.Mark(int32(id),"call_end")\n\t\treturn r.result, r.err')
s=s.replace('var msg struct {','frameAt:=base.ObsNow()\n var msg struct {')
s=s.replace('p.mu.Lock()\n\t\tch := p.pending[msg.ID]','p.obs.At(int32(msg.ID),"host_frame",frameAt);p.obs.Mark(int32(msg.ID),"host_decode")\n p.mu.Lock()\n\t\tch := p.pending[msg.ID]')
s=s.replace('ch <- response{result: msg.Result','p.obs.Mark(int32(msg.ID),"notify_begin")\n ch <- response{result: msg.Result');put(rel,s)
put(base+'observation.go','''package base
import("encoding/json";"os";"sync";"time";"sync/atomic")
var ObsEnabled=os.Getenv("INSERT_STAGES")=="1"
var obsEpoch=time.Now()
var obsAllMu sync.Mutex
var obsAll []*ObsInstance
var obsSerial atomic.Int64
type ObsEvent struct{ID int32; Name string; NS int64}
type ObsInstance struct{Serial int64;Label string;mu sync.Mutex;Events []ObsEvent}
func ObsNow()int64{if !ObsEnabled{return 0};return time.Since(obsEpoch).Nanoseconds()}
func NewObs(label string)*ObsInstance{o:=&ObsInstance{Serial:obsSerial.Add(1),Label:label,Events:make([]ObsEvent,0,3000)};obsAllMu.Lock();obsAll=append(obsAll,o);obsAllMu.Unlock();return o}
func(o *ObsInstance)At(id int32,name string,ns int64){if o==nil||!experimentPhase.Load(){return};o.mu.Lock();o.Events=append(o.Events,ObsEvent{id,name,ns});o.mu.Unlock()}
func(o *ObsInstance)Mark(id int32,name string){if o!=nil{o.At(id,name,ObsNow())}}
func ObsDump(path string)error{if path==""{return nil};b,e:=json.Marshal(obsAll);if e!=nil{return e};return os.WriteFile(path,b,0644)}
''')
put('internal/guest/observation_reader.go','''package guest
import("io";"encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")
type obsReader struct{io.Reader;obs *base.ObsInstance;buf []byte}
func(r *obsReader)Observation()*base.ObsInstance{return r.obs}
func(r *obsReader)Read(b []byte)(int,error){n,e:=r.Reader.Read(b);r.buf=append(r.buf,b[:n]...);for len(r.buf)>=4 {l:=binary.LittleEndian.Uint32(r.buf);if l==0||l==0xfffffffe{r.buf=r.buf[4:];continue};if l>32<<20+9{panic("observer oversize")};if len(r.buf)<int(l)+4{break};if l<9{panic("observer short")};id:=int32(binary.LittleEndian.Uint32(r.buf[5:]));r.obs.Mark(id,"guest_frame");r.buf=r.buf[4+int(l):]};return n,e}
''')
edit('experiment_stages.go','func ExperimentDump(path string)error{return base.ExperimentDump(path)}','func ExperimentDump(path string)error{if err:=base.ObsDump(os.Getenv("OBS_FILE"));err!=nil{return err};return base.ExperimentDump(path)}\n func ExperimentClock()int64{return base.ObsNow()}')
edit('experiment_stages.go','import "github.com/masahitojp/mariamem/internal/generatedgo/code/base"','import "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\n import "os"')
p=T/'maria/store/insert_stage_test.go';s=p.read_text().replace('"strings"','"strings";"encoding/json";"runtime/pprof"')
s=s.replace('func TestInsertOnly(t *testing.T){runProbe(t,true)}','''func TestInsertOnly(t *testing.T){waves:=1;if os.Getenv("PROFILE_ONLY")=="1"{waves=8};for i:=0;i<waves;i++{os.Setenv("WAVE_INDEX",strconv.Itoa(i));runProbe(t,true)}}''')
s=s.replace('orders []store.SampleOrder','orders []store.SampleOrder;times [][2]int64')
s=s.replace('c.s,e=fx.probeSnap.Fork(ctx)','c.s,e=fx.probeSnap.Fork(context.WithValue(ctx,"mariamem_benchmark_label",c.label))')
s=s.replace('pgmem.ExperimentPhase(true)','''var pf *os.File
  if os.Getenv("PROFILE_ONLY")=="1" {var er error;pf,er=os.Create(os.Getenv("PROFILE_DIR")+"/wave-"+os.Getenv("WAVE_INDEX")+".pprof");if er!=nil{t.Fatal(er)};if er=pprof.StartCPUProfile(pf);er!=nil{t.Fatal(er)}}
  pgmem.ExperimentPhase(true)''')
s=s.replace('pgmem.ExperimentPhase(false)','''pgmem.ExperimentPhase(false)
  if pf!=nil{pprof.StopCPUProfile();if e:=pf.Close();e!=nil{t.Fatal(e)}}
  if os.Getenv("CLIENT_FILE")!=""{b,_:=json.Marshal(childrenTimes(children));if e:=os.WriteFile(os.Getenv("CLIENT_FILE"),b,0644);e!=nil{t.Fatal(e)}}''')
s=s.replace('if _,e:=c.stmt.ExecContext(ctx,o.ID,it.ProductID,it.Quantity,it.UnitPriceCents);e!=nil{return e}','a:=pgmem.ExperimentClock();_,e:=c.stmt.ExecContext(ctx,o.ID,it.ProductID,it.Quantity,it.UnitPriceCents);z:=pgmem.ExperimentClock();c.times=append(c.times,[2]int64{a,z});if e!=nil{return e}')
s+='\nfunc childrenTimes(cs []probeChild)map[string][][2]int64{r:=map[string][][2]int64{};for _,c:=range cs{r[c.label]=c.times};return r}\n';p.write_text(s)
(E/'overlay.json').write_text(json.dumps(o,indent=2));(E/'setup188.py').write_bytes(Path(__file__).read_bytes())
# baseline tool logs/data are inherited only for replay; new measurement names live in campaign188/.
