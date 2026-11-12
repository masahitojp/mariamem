"""Inject the historical caller collector, preserving current SQL and product sources."""
from pathlib import Path
import hashlib,json,subprocess,sys,re
root,runner=map(Path,sys.argv[1:]);old='7e6547f95b84b12c608a88c39221da62da4ce256'
def get(name):return subprocess.check_output(['git','show',old+':benchmarks/issue88modelcase/maria/store/'+name],cwd=root,text=True)
def edit(path,a,b):
 s=path.read_text();assert s.count(a)==1,(path,a);path.write_text(s.replace(a,b))
d=runner/'maria/store';before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob('*.go')}
s=(d/'seed.go').read_text();replacement=get('seed.go')
a=s.index('func LoadSample(');b=s.index('// ResetSample',a);aa=replacement.index('func LoadSample(');bb=replacement.index('// ResetSample',aa)
assert s[:a]==replacement[:aa] and s[b:]==replacement[bb:]
assert re.findall(r'`[^`]*`',s[a:b])==re.findall(r'`[^`]*`',replacement[aa:bb]), 'SQL literals/order changed'
(d/'seed.go').write_text(s[:a]+replacement[aa:bb]+s[b:])
for name in ['sample_observe.go','prepare_capture.go']:(d/name).write_text(get(name))
p=d/'sample_observe.go';edit(p,'if phase == "prepare" {','if true {')
p=d/'prepare_capture.go';edit(p,'`json:"prepare_ordinal"`','`json:"operation_ordinal"`')
p=d/'backend_test.go';edit(p,'"strconv"','"strconv"\n"runtime/pprof"\n"sync/atomic"')
edit(p,'func wrap(d *mariamem.Database) *database {','''var dbSequence atomic.Int32
func labeledStart(ctx context.Context, f func(context.Context) (*mariamem.Database,error)) (*database,error) {
 id:=fmt.Sprintf("uca-db-%d",dbSequence.Add(1))
 var d *mariamem.Database;var err error
 pprof.Do(ctx,pprof.Labels("db_id",id),func(ctx context.Context){d,err=f(ctx)})
 if err!=nil{return nil,err};return wrap(d,id),nil
}
func wrap(d *mariamem.Database, id string) *database {''')
edit(p,'return &database{open:', 'return &database{id:id, open:')
edit(p,'''c, e := s.Fork(observeContext(ctx, lane))
			if e != nil {
				return nil, e
			}
			return wrap(c), nil''','return labeledStart(observeContext(ctx,lane),s.Fork)')
edit(p,'''d, e := mariamem.Start(observeContext(ctx, "root"), mariamem.Options{})
	if e != nil {
		return nil, e
	}
	return wrap(d), nil''','return labeledStart(observeContext(ctx,"root"),func(ctx context.Context)(*mariamem.Database,error){return mariamem.Start(ctx,mariamem.Options{})})')
p=d/'fixture_test.go';edit(p,'"context"','"context"\n"encoding/json"');edit(p,'type database struct {','type database struct {\nid string')
oldfixture=get('fixture_test.go');a=oldfixture.index('var sampleRecords');b=oldfixture.index('func must(',a)
edit(p,'var fx *fixture','var fx *fixture\n'+oldfixture[a:b])
edit(p,'checkSettings(p, fx.rec)','''checkSettings(p,fx.rec)
 if os.Getenv("ISSUE68_CONTROL")=="1" {
 var n int;must(store.CapturePositiveControl(sampleContext("positive_control",root.id),func()error{return p.QueryRow("SELECT SLEEP(0.25)").Scan(&n)}));if n!=0{panic("sleep oracle")}
 }''')
edit(p,'store.LoadSample(context.Background(), f.sharedDB)','store.LoadSample(sampleContext("shared",f.sharedOwner.id), f.sharedDB)')
edit(p,'store.LoadSample(context.Background(), p)','store.LoadSample(sampleContext(t.Name(),owner.id), p)')
edit(p,'must(writeForkObservations(os.Getenv("FORK_STAGE_PATH")))','''must(writeForkObservations(os.Getenv("FORK_STAGE_PATH")))
 if path:=os.Getenv("SAMPLE_PHASES_OUT");path!=""{data,e:=json.Marshal(sampleRecords);must(e);must(os.WriteFile(path,data,0600))}
 must(store.WritePrepareCaptures(os.Getenv("ISSUE68_CAPTURE_DIR")))''')
# Historical collector clock is added only if this immutable harness lacks it.
p=runner/'internal/trace/trace.go';s=p.read_text()
if 'func (r *Recorder) OffsetUS()' not in s:
 assert 't0    time.Time' in s
 p.write_text(s+'\nfunc (r *Recorder) OffsetUS() int64 { return time.Since(r.t0).Microseconds() }\n')
subprocess.run(['gofmt','-w',str(p),*map(str,d.glob('*.go'))],check=True)
after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob('*.go')}
(runner/'diagnostic-injection.json').write_text(json.dumps({'collector_source_commit':old,'before':before,'after':after,'product_changed':False},indent=2)+'\n')
