from pathlib import Path
import subprocess,json,sys
S,P,T=map(Path,sys.argv[1:]);R=P/'tests/timer_calibration/runner';D=R/'maria/store'
def edit(p,a,b):
 s=p.read_text();assert s.count(a)==1,(p,a);p.write_text(s.replace(a,b))
p=D/'backend_test.go';edit(p,'func startBackend(ctx context.Context) (*database, error) {','func startBackend(ctx context.Context) (*database, error) {\nbase.InitReadObservation(fx.rec.OffsetUS)')
p=D/'fixture_test.go';edit(p,'"context"','"context"\n"github.com/masahitojp/mariamem/internal/generatedgo/code/base"');edit(p,'must(store.WritePrepareCaptures(os.Getenv("ISSUE68_CAPTURE_DIR")))','must(store.WritePrepareCaptures(os.Getenv("ISSUE68_CAPTURE_DIR")))\nmust(base.WriteReadObservation(os.Getenv("READ_OBSERVATION_OUT")))')
s=subprocess.check_output(['git','show','bcab9e6e:benchmarks/issue88modelcase/maria/store/prepare_capture.go'],cwd=S,text=True).replace('`json:"prepare_ordinal"`','`json:"operation_ordinal"`');(D/'prepare_capture.go').write_text(s)
subprocess.run(['gofmt','-w',*map(str,D.glob('*.go'))],check=True)
print('HARNESS READY: fixed SQL, shared clock, bounded same-DB capture')
