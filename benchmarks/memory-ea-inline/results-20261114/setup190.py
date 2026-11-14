from pathlib import Path
import json,subprocess,tarfile,io,shutil,difflib
W=Path('build/experiment-work/memory-ea-inline').resolve();E=W/'evidence';T=W/'temp';S=W/'worktree'
prefix='benchmarks/insert-trigger-stages/results-20261114/sum-control/'
t=tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive','706072d8',prefix])))
for m in t.getmembers():
 if m.isfile() and (m.name.startswith(prefix+'harness/')or m.name[len(prefix):]in ['restore.py','extend.py','bindings.json','preserved-hashes.json','plan.json','overlay-experiment_stages.go','overlay-internal_generatedgo_code_base_experiment_stages.go']):
  p=E/m.name[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
subprocess.run(['python3',str(E/'restore.py')],check=True);subprocess.run(['python3',str(E/'extend.py')],check=True)
p=S/'benchmarks/spikes/wasm2go/pure-memory32.patch';s=p.read_text();a='+func memoryEA(m *Module, addr, offset, size uint64) uint64 {\n+\tif !memoryInBounds(m, addr, offset, size) {\n+\t\twasm_trap_memory_oob()';b=a.replace('wasm_trap_memory_oob()','panic("wasm: memory access out of bounds")');assert s.count(a)==1;p.write_text(s.replace(a,b))
o=json.loads((E/'overlay.json').read_text());baseline=o['Replace'];candidate=dict(baseline)
key=str(S/'internal/generatedgo/code/base/base.go');p=Path(baseline[key]);s=p.read_text();a='func MemoryEA(m *Module, addr, offset, size uint64) uint64 {\n\tif !MemoryInBounds(m, addr, offset, size) {\n\t\tWasm_trap_memory_oob()';b=a.replace('Wasm_trap_memory_oob()','panic("wasm: memory access out of bounds")');assert s.count(a)==1;out=T/'candidate-base.go';out.write_text(s.replace(a,b));candidate[key]=str(out)
for label,r in [('baseline',baseline),('candidate',candidate)]:
 (E/(label+'-overlay.json')).write_text(json.dumps({'Replace':r},indent=2))
(E/'candidate.patch').write_text(''.join(difflib.unified_diff(s.splitlines(True),out.read_text().splitlines(True),fromfile='baseline/base.go',tofile='candidate/base.go',n=0)))
p=T/'memory-ea-property_test.go';shutil.copy(E/'memory-ea-property_test.go',p)
for label in ['baseline','candidate']:
 pth=E/(label+'-overlay.json');d=json.loads(pth.read_text());d['Replace'][str(S/'internal/generatedgo/code/base/memory_ea_property_test.go')]=str(p);pth.write_text(json.dumps(d,indent=2))
