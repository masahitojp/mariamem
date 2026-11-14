package base
import("encoding/json";"os";"sync";"sync/atomic";"time";"fmt")
var experimentEnabled=os.Getenv("INSERT_STAGES")=="1"
var experimentPhase atomic.Bool
var experimentOrigin=time.Now()
var experimentMu sync.Mutex
var experimentModules []*Module
type ExperimentRecord struct{ID int32; T [7]int64; Counts [7]int; WriteNS int64; Writes int}
func ExperimentNow()int64{return time.Since(experimentOrigin).Nanoseconds()}
func ExperimentPhase(on bool){experimentPhase.Store(on)}
func ExperimentBegin(m *Module,id int32){
 if !experimentEnabled||!experimentPhase.Load(){return}
 if m.ExperimentCurrent!=nil{panic("overlapping request")}
 if m.ExperimentRecords==nil{m.ExperimentRecords=make([]ExperimentRecord,0,128);experimentMu.Lock();experimentModules=append(experimentModules,m);experimentMu.Unlock()}
 m.ExperimentRecords=append(m.ExperimentRecords,ExperimentRecord{ID:id});m.ExperimentCurrent=&m.ExperimentRecords[len(m.ExperimentRecords)-1];ExperimentMark(m,0)
}
func ExperimentMark(m *Module,i int){if r:=m.ExperimentCurrent;r!=nil{r.T[i]=ExperimentNow();r.Counts[i]++}}
func ExperimentEnd(m *Module){ExperimentMark(m,6);m.ExperimentCurrent=nil}
func ExperimentWriteEnd(m *Module,start int64){if r:=m.ExperimentCurrent;r!=nil{r.WriteNS+=ExperimentNow()-start;r.Writes++}}
// Called after all children and the fixture have been closed/joined.
func ExperimentDump(path string)error{if path==""{return nil};out:=make([]map[string]any,0);for _,m:=range experimentModules{if m.ExperimentCurrent!=nil{return fmt.Errorf("unfinished request")};out=append(out,map[string]any{"module":fmt.Sprintf("%p",m),"records":m.ExperimentRecords})};b,e:=json.Marshal(out);if e!=nil{return e};return os.WriteFile(path,b,0644)}
