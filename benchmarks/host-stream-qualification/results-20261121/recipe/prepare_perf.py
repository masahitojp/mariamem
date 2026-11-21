"""Keep the pinned fixture/oracles; synchronize eight workers around only the SQL window."""
from pathlib import Path
import subprocess,sys
w=Path(sys.argv[1]).resolve();t=w/'temp';h=t/'harness';rec=Path(__file__).resolve().parent
ck='7c5893b3d5198d2c5087dbb100e631dfe63a58bb:benchmarks/trigger-sum-bottleneck/results-20261121/recipe/'
for f in ('main.go','restore.py'):
    (t/f).write_bytes(subprocess.check_output(['git','show',ck+f],cwd=w/'worktree'))
subprocess.run([sys.executable,t/'restore.py',h,w/'worktree'],check=True)
s=(h/'main.go').read_text()
def rep(old,new):
    global s
    assert s.count(old)==1,old
    s=s.replace(old,new)
rep('"runtime/pprof"','')
rep('"time"','')
rep('maria.SnapshotOptions{}','maria.SnapshotOptions{MaxForks:8}')
rep('n int, want map[string]string) time.Duration','n int, want map[string]string, gate *waveGate)')
start=s.index('bodies := triggers(db, want)');end=s.index('check(count',start)
s=s[:start]+'triggers(db,want)\n\t'+s[end:]
rep('start := time.Now()','gate.start()')
rep('elapsed := time.Since(start)','gate.end()')
rep('return elapsed','return')
i=s.index('func run()')
s=s[:i]+'''func run(){
 if *work=="mixed" || *work=="large" {for n:=0;n<*waves;n++{shared(n)};return}
 *arm=*work
 want:=reference();must(os.Setenv("MARIA_AUDIT_OF","1"));must(os.Setenv("MODELCASE_MATCHED","1"))
 mode:="sum";if *arm=="B"{mode="incremental"};must(os.Setenv("SUM_EXPERIMENT",mode))
 orders:=store.SampleOrders();snap:=baseline(orders);defer func(){must(snap.Close())}()
 for n:=0;n<*waves;n++{wave(n,func(i int,g *waveGate){batch(snap,orders,i,want,g)})}
}
func main(){flag.Parse();run()}
'''
(h/'main.go').write_text(s)
(h/'waves.go').write_bytes((rec/'waves.go.txt').read_bytes())
