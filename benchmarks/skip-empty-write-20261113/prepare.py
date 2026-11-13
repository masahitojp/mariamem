from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];prefix='benchmarks/modelcase-default-ipc-20261113/maria-harness/'
for f in subprocess.check_output(['git','ls-tree','-r','--name-only','experiment/modelcase-default-ipc',prefix],text=True).splitlines():
 p=r/'temp/maria'/f[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show','experiment/modelcase-default-ipc:'+f]))
p=r/'evidence/ipc_overlay.py';p.write_bytes(subprocess.check_output(['git','show','experiment/modelcase-default-ipc:benchmarks/modelcase-default-ipc-20261113/ipc_overlay.py']))
subprocess.run(['python3',str(p)],check=True)
src=r/'worktree/internal/generatedgo/code/base/base.go';s=src.read_text();anchor='func writeVec(dst io.Writer, bufs [][]byte) (uint64, error) {\n\tvar total uint64\n\tfor _, buf := range bufs {'
assert s.count(anchor)==1
replacement='''// Disposable spike, selected once per process; canonical generator is unchanged.
var experimentSkipEmptyWrite = os.Getenv("MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE") == "1"

func writeVec(dst io.Writer, bufs [][]byte) (uint64, error) {
 hasData := false
 if experimentSkipEmptyWrite {
  for _, b := range bufs {if len(b)>0 {hasData=true;break}}
 }
 var total uint64
 for _, buf := range bufs {
  // Preserve all-empty writes, including errors from closed destinations.
  if hasData && len(buf)==0 {continue}
'''
s=s.replace(anchor,replacement);dst=r/'temp/base_overlay.go';dst.write_text(s)
p=r/'evidence/overlay.json';o=json.loads(p.read_text());o['Replace'][str(src)]=str(dst);o['Replace'][str(src.parent/'experiment_empty_write_test.go')]=str(r/'temp/experiment_empty_write_test.go');p.write_text(json.dumps(o,indent=2))
(r/'evidence/plan.json').write_text(json.dumps({'question':'skip empty iovecs in mixed vectors; preserve all-empty, FD and memory validation, errors/progress','source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','harness_commit':'d6ddbc7b0ddb0c2dc31ec4b8c8ed8478e0b4b694','interpolation':'inherit true','same_binary':'runtime switch read once, baseline false/candidate true','unit_boundaries':['wasm32/64 fd_write','invalid fd/memory','all-empty closed writer','mixed prefix/middle/suffix empties','short write/errors','framed transport/cancellation package tests'],'primary':'1 warmup each +5 alternating pairs; wall,user/system CPU,70 tests each','counter':'3 alternating observer-on pairs; bytes/frame equality,22 joined DBs each,baseline/candidate empty write counts','budgets':{'gib':10,'min_free_gib':12,'build_s':1800,'process_s':130,'measure_s':900},'exit':'mechanical suppression + correctness + measured speed/CPU, or preserve negative result; no extra repeats','adoption':'experiment only, no main/guest regeneration/release'},indent=2))
