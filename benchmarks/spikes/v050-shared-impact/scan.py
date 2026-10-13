"""Map checksum-bound real WASM disassembly to canonical source, not a race census."""
from pathlib import Path
import argparse,collections,hashlib,json,re
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--wasm',type=Path,required=True);p.add_argument('--wat',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.root.resolve();a.output.mkdir(parents=True,exist_ok=True)
def h(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def save(name,x):(a.output/name).write_text(json.dumps(x,indent=2)+'\n')
assert h(a.wasm)==json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
mp=root/'docs/reviews/v050-ad-integration-evidence/function-map.txt';names={int(i):n for i,n in (l.split(':',1) for l in mp.read_text().splitlines())}
assert h(mp)==json.loads((root/'release/generated-license-evidence.json').read_text())['symbol_map_sha256']
imports=0;fn=None;defs=[];wasm=[];calls=collections.defaultdict(set);tables=set()
for line_no,l in enumerate(a.wat.open(),1):
 if re.match(r' \(import.*\(func ',l):imports+=1
 m=re.match(r' \(func \$(\d+)',l)
 if m:defs.append(int(m[1]));fn=int(m[1])+imports
 if l.startswith(' (elem'):
  tables.update(int(x)+imports for x in re.findall(r'\$(\d+)',l))
 if fn is None:continue
 for c in re.findall(r'\(call \$(\d+)\b',l):calls[fn].add(int(c)+imports)
 op=re.search(r'\((i(?:32|64)\.atomic\.(?:store(?:8|16)|rmw(?:8|16)\.\w+)(?:_u)?)\b([^\n]*)',l)
 if op:wasm.append({'fn':fn,'symbol':names.get(fn),'wat_line':line_no,'opcode':op[1],'attributes':op[2].strip()})
assert defs==list(range(len(defs))) and len(defs)+imports==len(names)
generated=[]
for f in sorted((root/'internal/generatedgo/code').glob('p*/*.go')):
 fn=None
 for n,l in enumerate(f.read_text().splitlines(),1):
  m=re.match(r'func Fn(\d+)\(',l)
  if m:fn=int(m[1])
  for op in re.finditer(r'base\.(Atomic(?:Store|Rmw)\w*_(?:8|16)\w*)\(',l):generated.append({'fn':fn,'symbol':names.get(fn),'file':f.relative_to(root).as_posix(),'line':n,'helper':op[1],'statement':l.strip()})
for x in generated:
 x['wasm_direct_callers']=[{'fn':f,'symbol':names.get(f)} for f in calls if x['fn'] in calls[f]]
 x['wasm_table_member']=x['fn'] in tables
 x['same_function_wasm_sites']=[y for y in wasm if y['fn']==x['fn']]
 x['narrow_direct_callees']=[y for y in wasm if y['fn'] in calls[x['fn']]]
save('wasm-sites.json',wasm);save('generated-sites.json',generated);save('wasm-calls.json',{str(k):sorted(v) for k,v in calls.items()})
save('scan-summary.json',{'wasm_sha256':h(a.wasm),'wat_sha256':h(a.wat),'function_map_sha256':h(mp),'imports':imports,'definitions':len(defs),'wasm_sites':len(wasm),'generated_sites':len(generated),'wasm_counts':dict(collections.Counter(x['opcode'] for x in wasm)),'generated_counts':dict(collections.Counter(x['helper'] for x in generated)),'warning':'Counts differ when control flow/callees are expanded. Direct and table callers are conservative edges, not path or field ownership proofs. Disassembly must be produced from this same Wasm by recorded Binaryen command.'})
print('PASS: fixed guest, function index space, opcode and generated helper mapping')
