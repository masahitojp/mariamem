import json,sys
from pathlib import Path
r=Path(sys.argv[1]).resolve();t=Path(sys.argv[2]).resolve();t.mkdir(exist_ok=True)
p=r/'internal/generatedgo/code/base/base.go';s=p.read_text()
old="func writeVec(dst io.Writer, bufs [][]byte) (uint64, error) {\n\tvar total uint64\n\tfor _, buf := range bufs {"
new="""var experimentSkipEmptyWrite = os.Getenv("MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE") == "1"
func writeVec(dst io.Writer, bufs [][]byte) (uint64, error) {
 hasData := false
 if experimentSkipEmptyWrite {
  for _, b := range bufs {if len(b)>0 {hasData=true;break}}
 }
 var total uint64
 for _, buf := range bufs {
  if hasData && len(buf)==0 {continue}
"""
assert s.count(old)==1
q=t/'base.go';q.write_text(s.replace(old,new))
a=r/'internal/generatedgo/code/base/experiment_empty_write_test.go';b=r/'benchmarks/response-empty-write/experiment_empty_write_test.go.txt'
(t/'overlay.json').write_text(json.dumps({'Replace':{str(p):str(q),str(a):str(b)}}))
