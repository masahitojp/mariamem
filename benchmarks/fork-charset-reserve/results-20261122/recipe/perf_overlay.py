"""Apply the same capacity test without any diagnostic hooks."""
import json
from pathlib import Path

w=Path.cwd()
source=w/'worktree/internal/generatedgo/code'
temp=w/'temp'
body=source/'p1/p1_pure.go'
base=source/'base/base.go'
sites=json.loads((temp/'overlay.json').read_text())['Replace']
observed=Path(sites[str(body)]).read_text()
before='Fn809(m, v55, int32(18934864), int32(16), int32(18520540), int32(64), v60, v60, int32(554), v60, int32(1))'
after=before.replace('int32(64)','base.CollationHashReserve()')
original=body.read_text()
assert original.count(before)==1 and observed.count(after)==1
part=temp/'perf-p1_pure.go'
part.write_text(original.replace(before,after))
helper=(w/'evidence/recipe/measure_fn.go.txt').read_text().split('// The experiment changes only')[1]
impl=temp/'perf-base.go'
impl.write_text(base.read_text()+'\n// The experiment changes only'+helper)
(temp/'perf-overlay.json').write_text(json.dumps({'Replace':{str(body):str(part),str(base):str(impl)}}))
