package base
import("encoding/json";"os";"sync";"time";"sync/atomic")
var ObsEnabled=os.Getenv("INSERT_STAGES")=="1"
var obsEpoch=time.Now()
var obsAllMu sync.Mutex
var obsAll []*ObsInstance
var obsSerial atomic.Int64
type ObsEvent struct{ID int32; Name string; NS int64}
type ObsInstance struct{Serial int64;Label string;mu sync.Mutex;Events []ObsEvent;seen map[int32]bool}
func ObsNow()int64{if !ObsEnabled{return 0};return time.Since(obsEpoch).Nanoseconds()}
func NewObs(label string)*ObsInstance{o:=&ObsInstance{Serial:obsSerial.Add(1),Label:label,Events:make([]ObsEvent,0,3000)};obsAllMu.Lock();obsAll=append(obsAll,o);obsAllMu.Unlock();return o}
func(o *ObsInstance)At(id int32,name string,ns int64){if o==nil{return};o.mu.Lock();defer o.mu.Unlock();if o.seen==nil{o.seen=map[int32]bool{}};if !experimentPhase.Load()&&!o.seen[id]{return};o.seen[id]=true;o.Events=append(o.Events,ObsEvent{id,name,ns})}
func(o *ObsInstance)Mark(id int32,name string){if o!=nil{o.At(id,name,ObsNow())}}
func ObsDump(path string)error{if path==""{return nil};b,e:=json.Marshal(obsAll);if e!=nil{return e};return os.WriteFile(path,b,0644)}
