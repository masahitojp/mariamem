from pathlib import Path
import json,hashlib,sys,subprocess
s,o=map(lambda x:Path(x).resolve(),sys.argv[1:3]);o.mkdir(parents=True,exist_ok=True);b=s/'benchmarks/lexerprepared'
proof=json.loads((b/'source-proof.json').read_text())
for rel,h in proof.items():assert hashlib.sha256((s/rel).read_bytes()).hexdigest()==h,rel
table=json.loads((b/'tables.json').read_text());prior=s/'benchmarks/lexermap/results/summary.json'
assert hashlib.sha256(prior.read_bytes()).hexdigest()==table['input_summary_sha256']
a=json.loads(prior.read_text());hs=sorted(a['map_pairs']);data=b''.join(bytes.fromhex(a['map_pairs'][h]) for h in hs)
assert data.hex()==table['data_hex'] and hashlib.sha256(data).hexdigest()==table['data_sha256']
expected={str(x['descriptor_offset']):{'number':x['number'],'pair':hs.index(x['pair_sha256'])} for x in a['bindings']};assert expected==table['bindings']
mapping={};hashes=[]
if '--undo' in sys.argv:
 subprocess.run([sys.executable,str(s/'benchmarks/undorelay/overlay.py'),str(s),str(o/'undo')],check=True)
 mapping=json.loads((o/'undo/overlay.json').read_text())['Replace']
 hashes=json.loads((o/'undo/hashes.json').read_text())
def read(rel):return Path(mapping.get(str(s/rel),s/rel)).read_text()
def put(rel,text):
 p=s/rel;dest=o/rel.replace("/","_");dest.write_text(text);mapping[str(p)]=str(dest)
 row={'path':rel,'before_sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'after_sha256':hashlib.sha256(text.encode()).hexdigest()}
 hashes[:]=[x for x in hashes if x['path']!=rel];hashes.append(row)
rel='internal/generatedgo/code/base/base.go';v=read(rel);assert v.count('type Module struct {')==1;put(rel,v.replace('type Module struct {','type Module struct {\n LPBase uint32\n LPFallbackChecked bool',1))
rel='internal/generatedgo/code/p1/p1_pure.go';v=read(rel);old='v2052 = Fn955(m, v2045)';assert v.count(old)==1;put(rel,v.replace(old,'v2052 = LPCompiled(m, v2045)',1))
rel='internal/generatedgo/code/p1/alias.go';put(rel,read(rel)+'\n//go:linkname LPCompiled github.com/masahitojp/mariamem/internal/generatedgo/code/p4.LPCompiled\nfunc LPCompiled(m *base.Module, cs int32) int32\n')
put('internal/generatedgo/code/p4/lexer_prepared.go','package p4\nimport base "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\nfunc LPCompiled(m *base.Module,cs int32)int32{return base.LPCompiled(m,cs,Fn955,Fn766)}\n')
put('internal/generatedgo/code/base/lexer_prepared.go',(b/'prepared.go.txt').read_text())
put('internal/generatedgo/code/base/lexer_prepared_test.go',(b/'prepared_test.go.txt').read_text())
go='package base\nimport "encoding/hex"\nvar lpData=func()[]byte{b,e:=hex.DecodeString("'+data.hex()+'");if e!=nil{panic(e)};return b}()\nconst lpSHA="'+table['data_sha256']+'"\nvar lpBindings=map[uint32]lpBinding{\n'
for p,v in sorted(table['bindings'].items(),key=lambda t:int(t[0])):go+=f'{p}:{{{v["number"]},{v["pair"]}}},\n'
put('internal/generatedgo/code/base/lexer_tables.go',go+'}\n')
(o/'overlay.json').write_text(json.dumps({'Replace':mapping},indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
