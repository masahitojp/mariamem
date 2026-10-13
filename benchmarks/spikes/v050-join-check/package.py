"""Copy original join/unlock/allocator bodies; instrument only a disposable host wake."""
import argparse,hashlib,json,re,shutil,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 graph=json.loads((ROOT/'docs/reviews/v050-access-paths-evidence/direct-call-graph.json').read_text());provenance=json.loads((ROOT/'internal/generatedgo/provenance.json').read_text())
 seen=set();todo=[217,221,152]
 while todo:
  f=todo.pop()
  if f in seen:continue
  seen.add(f);todo.extend(graph[str(f)]['direct_callees'])
 assert all(graph[str(f)]['indirect_calls']==0 for f in seen)
 module=out/'module';module.mkdir();(module/'go.mod').write_text('module github.com/masahitojp/mariamem\n\ngo 1.26.0\n')
 copied={}
 for relative in ['internal/generatedgo/code/base','internal/prepared']:
  target=module/relative;target.mkdir(parents=True)
  for f in (ROOT/relative).iterdir():
   if f.suffix in ['.go','.s'] and not f.name.endswith('_test.go'):shutil.copyfile(f,target/f.name);copied[str(f.relative_to(ROOT))]=sha(f)
 probe=module/'probe';probe.mkdir();defs=[];identities={}
 for f in sorted(seen):
  info=graph[str(f)];source=ROOT/info['file'];assert sha(source)==provenance['files_sha256'][info['file'].removeprefix('internal/generatedgo/')]
  lines=source.read_text().splitlines(True);start=info['line']-1;end=next((j for j in range(start+1,len(lines)) if re.match(r'func Fn\d+\(',lines[j])),len(lines));body=''.join(lines[start:end]);defs.append(body);identities[str(f)]={**info,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'source_sha256':sha(source)}
 headers='package probe\nimport("unsafe";"github.com/masahitojp/mariamem/internal/generatedgo/code/base"'+(';"sync/atomic"' if any('atomic.' in d for d in defs) else '')+')\n'
 (probe/'functions.go').write_text(headers+'\n'.join(defs))
 extract=runpy.run_path(str(ROOT/'benchmarks/spikes/v050-semantic-audit/package.py'))['host_method'];original=(ROOT/'internal/generatedgo/main.go').read_text()
 methods=[extract(original,n) for n in ['Futex_wait','futexWake','Futex_wake','Futex_wake_all']]
 anchor='base.AtomicNotify(m, addr, 0, count)';assert methods[1].count(anchor)==1;methods[1]=methods[1].replace(anchor,anchor+'\n if h.hook!=nil {h.hook(m,out)}')
 interface=(ROOT/'internal/generatedgo/code/base/base.go').read_text().split('type Wasix_32v1Imports interface {',1)[1].split('\n}',1)[0];unused=[]
 for line in interface.splitlines():
  if line.strip() and not line.strip().startswith(('Futex_wait(','Futex_wake(','Futex_wake_all(')):
   unused.append('func(h *host) '+line.strip().replace('*Module','*base.Module')+'{panic("unexpected import in bounded join fixture")}')
 (probe/'host.go').write_text('package probe\nimport("encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\ntype host struct{*base.WasiStubs;hook func(*base.Module,int32)}\n'+'\n'.join(methods+unused))
 source=ROOT/'internal/generatedgo/code/generated.go';assert sha(source)==provenance['files_sha256']['code/generated.go'];literal=re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)',source.read_text())[1];(probe/'data.bin').write_bytes(bytes.fromhex(literal.replace('\\x','')))
 shutil.copyfile(Path(__file__).with_name('probe_test.go.txt'),probe/'probe_test.go')
 (out/'identities.json').write_text(json.dumps({'functions':identities,'copied_source_sha256':copied,'host_source_sha256':sha(ROOT/'internal/generatedgo/main.go'),'observer':'one callback after AtomicNotify, before canonical output byte store; disposable fixture only','test_sha256':sha(Path(__file__).with_name('probe_test.go.txt'))},indent=2)+'\n');print(module)
if __name__=='__main__':main()
