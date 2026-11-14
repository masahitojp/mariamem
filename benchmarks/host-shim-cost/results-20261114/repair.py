from pathlib import Path
import json
W=Path('build/experiment-work/host-shim-cost').resolve();E=W/'evidence';T=W/'temp';S=W/'worktree';o=json.loads((E/'overlay.json').read_text());R=o['Replace'];p=Path(R[str(S/'internal/guest/guest.go')]);s=p.read_text();s=s.replace('id:=int32(binary.LittleEndian.Uint32(b[5:]));p.obs.Mark(id,"queue_begin")','var id int32;if len(b)>=9{id=int32(binary.LittleEndian.Uint32(b[5:]))};p.obs.Mark(id,"queue_begin")');p.write_text(s)
p=T/'obs-reader-test.go';s=p.read_text().replace('"testing";','"testing";"context";');s+='''
type obsBuffer struct{bytes.Buffer}
func(b *obsBuffer)Close()error{return nil}
func TestObsControlWrite(t *testing.T){b:=&obsBuffer{};p:=&Process{in:b,writes:make(chan struct{},1)};if e:=p.write(context.Background(),make([]byte,4));e!=nil||b.Len()!=4{t.Fatal(e,b.Len())}}
''';p.write_text(s)
p=E/'build.py';s=p.read_text().replace('^TestObsReader','^TestObs');p.write_text(s)
p=T/'maria/store/insert_stage_test.go';s=p.read_text().replace('"runtime/pprof"','"runtime/pprof";"time"');s=s.replace('var pf *os.File','var pf *os.File;window:=map[string]int64{};window["profiler_start_call_unix_ns"]=time.Now().UnixNano()');s=s.replace('pgmem.ExperimentPhase(true)','window["raw_start_unix_ns"]=time.Now().UnixNano()\n pgmem.ExperimentPhase(true)');s=s.replace('pgmem.ExperimentPhase(false)','pgmem.ExperimentPhase(false)\n window["raw_end_unix_ns"]=time.Now().UnixNano()');s=s.replace('if pf!=nil{pprof.StopCPUProfile();if e:=pf.Close();e!=nil{t.Fatal(e)}}','if pf!=nil{pprof.StopCPUProfile();window["profiler_stop_return_unix_ns"]=time.Now().UnixNano();if e:=pf.Close();e!=nil{t.Fatal(e)};b,_:=json.Marshal(window);if e:=os.WriteFile(os.Getenv("PROFILE_DIR")+"/wave-"+os.Getenv("WAVE_INDEX")+"-window.json",b,0644);e!=nil{t.Fatal(e)}}');p.write_text(s)
if (E/'campaign188').exists() and not (E/'failed-preflight-0').exists():(E/'campaign188').rename(E/'failed-preflight-0')
